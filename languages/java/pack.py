"""Java pack: pattern-based analysis over comment- and string-free code, plus the run agent.

The agent (agent/TrackerAgent.java) is built into tracker-agent.jar and loaded into
every JVM through the user's JAVA_TOOL_OPTIONS; it logs javac compiles and Java runs.
"""

import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from functools import lru_cache
from pathlib import Path

import settings
from languages import envvars
from languages.base import LanguagePack
from languages.java import eclipse_scan
from languages.java.analyzer import analyze_java

AGENT_DIR = Path(__file__).parent / "agent"
AGENT_SRC = AGENT_DIR / "TrackerAgent.java"
JAR_NAME = "tracker-agent.jar"
JAR_PATH = AGENT_DIR / JAR_NAME
MANIFEST = "Manifest-Version: 1.0\r\nPremain-Class: TrackerAgent\r\n\r\n"
BUILTIN_EXCLUDES = ("Program Files", "Program Files (x86)", "Windows", "AppData",
                    ".m2", ".gradle", ".p2", "node_modules")
NO_JAVAC = ("javac not found: Java will use the Eclipse-build scan only. "
            "Install a JDK or set JAVA_HOME, then re-run setup.")
_PROGRAM_FILES = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
JDK_ROOTS = [_PROGRAM_FILES / name for name in ("Java", "Eclipse Adoptium", "Microsoft", "Zulu")]
_EXE = ".exe" if os.name == "nt" else ""


def agent_token(jar_path):
    # Forward slashes: Windows and the JVM accept them, and no options parser can read them as escapes.
    return "-javaagent:" + str(jar_path).replace("\\", "/")


AGENT_TOKEN = agent_token(JAR_PATH)


class JavaPack(LanguagePack):
    key = "java"
    label = "Java"
    icon = "☕"
    editor = "Eclipse"
    extensions = {".java"}
    dir = Path(__file__).parent

    def analyze(self, source, path=None):
        return analyze_java(source, path)

    def install(self, lang_config, data_dir):
        return self.install_with_jar_path(JAR_PATH, lang_config, data_dir)

    def install_with_jar_path(self, jar_path, lang_config, data_dir):
        if " " in str(jar_path):
            return False, (f"Java agent not installed: its path contains a space ({jar_path}), which "
                           "JAVA_TOOL_OPTIONS can't hold. Move the tracker to a folder without spaces.")
        if find_javac() is None:
            return False, NO_JAVAC
        try:
            jar = build_agent(Path(jar_path).parent)
        except RuntimeError as e:
            return False, f"Java agent not installed: {e}"
        write_properties(jar.with_name("agent.properties"), lang_config, data_dir)
        # A dangling -javaagent stops every Java program, so only set it once the agent works.
        ok, message = self.self_test(lang_config, data_dir, jar_path=jar)
        if not ok:
            envvars.user_env_remove("JAVA_TOOL_OPTIONS", agent_token(jar))
            return False, f"Java agent not installed: {message}"
        envvars.user_env_add("JAVA_TOOL_OPTIONS", agent_token(jar))
        return True, "Java agent installed"

    def uninstall(self):
        removed = envvars.user_env_remove("JAVA_TOOL_OPTIONS", AGENT_TOKEN)
        return "Java agent removed" if removed else "Java agent was not set"

    def self_test(self, lang_config, data_dir=None, jar_path=None):
        """Run a throwaway class with exactly the JAVA_TOOL_OPTIONS token install would set."""
        jar = Path(jar_path or JAR_PATH)
        javac = find_javac()
        if javac is None:
            return False, "javac not found"
        if not jar.is_file():
            return False, f"agent jar not found ({jar})"
        try:
            with tempfile.TemporaryDirectory(prefix="javatracker_selftest_") as tmp:
                src, out, data = Path(tmp) / "code" / "src", Path(tmp) / "code" / "bin", Path(tmp) / "data"
                src.mkdir(parents=True)
                out.mkdir()  # JDK 8's javac won't create the -d folder
                (src / "Hello.java").write_text(
                    'public class Hello { public static void main(String[] a) { System.out.println("ok"); } }\n',
                    encoding="utf-8")
                result = subprocess.run([str(javac), "-d", str(out), str(src / "Hello.java")],
                                        capture_output=True, text=True, timeout=120, env=_clean_env())
                if result.returncode != 0:
                    return False, f"javac failed: {_first_line(result)}"
                # Temp is under AppData, so the built-in exclusions stay out of the test settings.
                props = Path(tmp) / "agent.properties"
                write_properties(props, {"exclude_folders": []}, data, builtin=False)
                env = _clean_env(JAVA_TOOL_OPTIONS=agent_token(jar), JAVATRACKER_PROPS=str(props))
                result = subprocess.run([str(java_for(javac)), "-cp", str(out), "Hello"],
                                        capture_output=True, text=True, timeout=60, env=env)
                noise = _stderr_noise(result.stderr)
                if result.returncode != 0 or noise:
                    return False, (noise or [f"java exited with code {result.returncode}"])[0]
                runs = data / "java" / "runs.jsonl"
                lines = runs.read_text(encoding="utf-8").splitlines() if runs.exists() else []
                if len(lines) == 1 and '"status": "success"' in lines[0]:
                    return True, "Java agent works"
                return False, "the agent did not log the test run"
        except Exception as e:
            return False, f"self-test failed: {e}"

    def collect(self, lang_config, data_dir, runs):
        """Prune runs of newly excluded folders, then log Eclipse builds found in the workspaces."""
        data_dir = Path(data_dir)
        is_excluded = eclipse_scan.is_excluded_factory(lang_config)
        if eclipse_scan.exclusions_changed(data_dir, lang_config):
            eclipse_scan.prune_excluded(data_dir, is_excluded, lang_config.get("exclude_folders", []))
            # Without this the installed agent keeps logging the folder that was just excluded.
            props = AGENT_DIR / "agent.properties"
            if props.is_file():
                try:
                    write_properties(props, lang_config, data_dir.parent, builtin=True)
                except OSError:
                    pass
        workspaces, seen = [], set()
        candidates = (eclipse_scan.recent_workspaces() + [Path(lang_config["code_folder"])]
                      + [Path(p) for p in lang_config.get("extra_workspaces", [])])
        for path in candidates:
            try:
                key = os.path.normcase(str(path.resolve()))
            except OSError:
                continue
            if key not in seen and path.is_dir():
                seen.add(key)
                workspaces.append(path)
        return eclipse_scan.scan_workspaces(workspaces, data_dir, runs, is_excluded)

    def extra_report(self, runs):
        """java_folders: the project folders worked in, newest first (top 15)."""
        folders = {}
        for run in runs:
            day = run["dt"].date().isoformat()
            files = {f.get("file") for f in run.get("files") or []} | {run.get("file")}
            for file in files - {None, ""}:
                entry = folders.setdefault(_source_root(file), {"files": set(), "last_seen": day})
                entry["files"].add(file)
                entry["last_seen"] = max(entry["last_seen"], day)
        rows = [{"folder": folder, "files": len(v["files"]), "last_seen": v["last_seen"]}
                for folder, v in folders.items()]
        rows.sort(key=lambda r: (r["last_seen"], r["folder"]), reverse=True)
        return {"java_folders": rows[:15]}

    def hook_installed(self):
        value = envvars.get_user_env("JAVA_TOOL_OPTIONS")
        try:
            return envvars._find(envvars._split(value), envvars._split(AGENT_TOKEN)) >= 0
        except ValueError:
            return False


def _source_root(file):
    """The folder above the first 'src' folder (the project), else the file's own folder."""
    parts = Path(file).parts
    for i, part in enumerate(parts):
        if part.lower() == "src" and i > 0:
            return str(Path(*parts[:i]))
    return str(Path(file).parent)


# ---------- finding a JDK and building the agent ----------

def _version_key(jdk_dir):
    """jdk1.8.0_511 -> (8, 0, 511); jdk-17.0.9.9-hotspot -> (17, 0, 9, 9)."""
    nums = [int(n) for n in re.findall(r"\d+", Path(jdk_dir).name)]
    if len(nums) > 1 and nums[0] == 1:
        nums = nums[1:]
    return tuple(nums)


def find_javac():
    """javac from PATH, then %JAVA_HOME%\\bin, then the newest JDK under Program Files."""
    found = shutil.which("javac")
    if found:
        return Path(found)
    home = os.environ.get("JAVA_HOME")
    if home and (Path(home) / "bin" / f"javac{_EXE}").is_file():
        return Path(home) / "bin" / f"javac{_EXE}"
    jdks = [d for root in JDK_ROOTS if root.is_dir()
            for d in list(root.glob("jdk*")) + list(root.glob("zulu*"))
            if (d / "bin" / f"javac{_EXE}").is_file()]
    if jdks:
        return max(jdks, key=_version_key) / "bin" / f"javac{_EXE}"
    return None


def java_for(javac):
    """The java launcher from the same JDK as javac."""
    java = Path(javac).with_name(f"java{_EXE}")
    if java.is_file():
        return java
    found = shutil.which("java")
    return Path(found) if found else None


@lru_cache(maxsize=None)
def javac_major(javac):
    # Java 8 prints its version on stderr, later ones on stdout.
    result = subprocess.run([str(javac), "-version"], capture_output=True, text=True, timeout=60,
                            env=_clean_env())
    return parse_javac_version(result.stdout + result.stderr)


def parse_javac_version(text):
    """8 for 'javac 1.8.0_511', 11 for 'javac 11.0.22', 17 for 'javac 17', 25 for 'javac 25-ea'; 0 if unknown."""
    match = re.search(r"javac (\d+)(?:\.(\d+))?", text)
    if not match:
        return 0
    major = int(match.group(1))
    return int(match.group(2) or 0) if major == 1 else major


def build_agent(out_dir):
    """Compile TrackerAgent.java for Java 8 and write out_dir/tracker-agent.jar."""
    javac = find_javac()
    if javac is None:
        raise RuntimeError("javac not found")
    # JDK 8's javac has no --release.
    target = ["--release", "8"] if javac_major(javac) >= 9 else ["-source", "1.8", "-target", "1.8"]
    with tempfile.TemporaryDirectory(prefix="javatracker_build_") as tmp:
        result = subprocess.run([str(javac), *target, "-encoding", "UTF-8", "-d", tmp, str(AGENT_SRC)],
                                capture_output=True, text=True, timeout=120, env=_clean_env())
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"javac exited with code {result.returncode}")
        data = _jar_bytes(Path(tmp))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jar = out_dir / JAR_NAME
    # Same bytes as last time: leave it, since running JVMs (Eclipse...) keep the jar locked.
    if not (jar.is_file() and jar.read_bytes() == data):
        try:
            jar.write_bytes(data)
        except OSError as e:
            raise RuntimeError(f"could not write {jar} ({e}). Close Eclipse and any running "
                               "Java programs, then re-run setup.") from e
    return jar


def _jar_bytes(classes_dir):
    # Fixed timestamps and order, so the same source always gives the same jar.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        entries = [("META-INF/MANIFEST.MF", MANIFEST.encode("ascii"))]
        entries += [(f.name, f.read_bytes()) for f in sorted(classes_dir.glob("*.class"))]
        for name, content in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, content)
    return buffer.getvalue()


def write_properties(path, lang_config, data_dir, builtin=True):
    """agent.properties: key=value lines, backslashes doubled (java.util.Properties escapes)."""
    exclude = (list(BUILTIN_EXCLUDES) if builtin else []) + list(lang_config.get("exclude_folders", []))
    values = {"data_dir": str(data_dir), "tracker_dir": str(settings.TRACKER_DIR), "exclude": ";".join(exclude)}
    text = "".join(f"{key}={value}\n".replace("\\", "\\\\") for key, value in values.items())
    Path(path).write_text(text, encoding="utf-8")


# Variables that add JVM options (and so may load agents or print notices) in our own child JVMs.
_JVM_OPTION_VARS = ("JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "JAVATRACKER_PROPS")
# The notices the JVM prints when one of them is set.
_JVM_NOTICES = ("Picked up JAVA_TOOL_OPTIONS:", "Picked up _JAVA_OPTIONS:", "NOTE: Picked up JDK_JAVA_OPTIONS:")


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in _JVM_OPTION_VARS}
    env.update(extra)
    return env


def _stderr_noise(stderr):
    """stderr lines other than the JVM's own 'Picked up ...' notices."""
    return [line for line in (stderr or "").splitlines()
            if line.strip() and not line.startswith(_JVM_NOTICES)]


def _first_line(result):
    lines = (result.stderr or result.stdout or "").strip().splitlines()
    return lines[0] if lines else f"exit code {result.returncode}"


PACK = JavaPack()
