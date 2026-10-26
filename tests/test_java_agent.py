import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from languages import get_pack
from languages.java import pack as jpack

JAVAC = jpack.find_javac()
JAVA = jpack.java_for(JAVAC) if JAVAC else None
JAVA_MAJOR = jpack.javac_major(JAVAC) if JAVAC else 0
NEEDS_JDK = unittest.skipUnless(JAVAC and JAVA, "no JDK found")


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("JAVA_TOOL_OPTIONS", "JAVATRACKER_PROPS")}
    env.update(extra)
    return env


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@NEEDS_JDK
class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jar_dir = Path(tempfile.mkdtemp(prefix="jagent_"))
        cls.jar = jpack.build_agent(cls.jar_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.jar_dir, ignore_errors=True)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jagent_case_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "data"
        self.code = self.tmp / "code"
        self.code.mkdir()
        self.write_props()

    def write_props(self, exclude=()):
        # The temp folder is under AppData, so the built-in exclusions are left out here.
        jpack.write_properties(self.jar.with_name("agent.properties"),
                               {"exclude_folders": list(exclude)}, self.data, builtin=False)

    def runs(self):
        return read_jsonl(self.data / "java" / "runs.jsonl")

    def run_java(self, *args, cwd=None):
        return subprocess.run([str(JAVA), f"-javaagent:{self.jar}", *map(str, args)], cwd=cwd or self.code,
                              capture_output=True, text=True, timeout=60, env=clean_env())

    def javac(self, *args, agent=True, cwd=None):
        cmd = [str(JAVAC)] + ([f"-J-javaagent:{self.jar}"] if agent else []) + list(map(str, args))
        return subprocess.run(cmd, cwd=cwd or self.code, capture_output=True, text=True, timeout=60,
                              env=clean_env())

    def project(self, root):
        src = root / "src" / "app"
        src.mkdir(parents=True)
        (src / "Main.java").write_text(
            "package app;\npublic class Main { public static void main(String[] a) {"
            " System.out.println(Helper.greet()); } }\n", encoding="utf-8")
        (src / "Helper.java").write_text(
            "package app;\nclass Helper { static String greet() { return \"hi\"; } }\n", encoding="utf-8")
        (src / "Boom.java").write_text(
            "package app;\npublic class Boom { public static void main(String[] a) {"
            " throw new IllegalStateException(\"boom\"); } }\n", encoding="utf-8")
        (root / "bin").mkdir()  # JDK 8's javac won't create the -d folder
        r = self.javac("-d", root / "bin", src / "Main.java", src / "Helper.java", src / "Boom.java",
                       agent=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        return src

    def test_compile_success_and_failure(self):
        (self.code / "Good.java").write_text("public class Good {}\n", encoding="utf-8")
        (self.code / "Bad.java").write_text("public class Bad { int x = ; }\n", encoding="utf-8")
        self.assertEqual(self.javac("Good.java").returncode, 0)
        self.assertNotEqual(self.javac("Bad.java").returncode, 0)
        lines = self.runs()
        self.assertEqual([l["status"] for l in lines], ["compiled", "compile_error"])
        self.assertEqual(lines[0]["source"], "javac")
        self.assertEqual((lines[0]["error_count"], lines[1]["error_count"]), (None, 1))
        self.assertEqual(lines[0]["file"], str(self.code / "Good.java"))
        sha = lines[0]["files"][0]["sha"]
        self.assertEqual(len(sha), 16)
        self.assertTrue((self.data / "java" / "snapshots" / f"{sha}.java").is_file())

    def test_compile_with_d_argfile_and_package(self):
        pkg = self.code / "src" / "app"
        pkg.mkdir(parents=True)
        (pkg / "A.java").write_text("package app;\npublic class A {}\n", encoding="utf-8")
        (pkg / "B.java").write_text("package app;\npublic class B {}\n", encoding="utf-8")
        # As javac reads it: backslashes escaped inside quotes, literal outside.
        quoted = str(pkg / "A.java").replace("\\", "\\\\")
        (self.code / "args.txt").write_text(f'# sources\n"{quoted}"\n{pkg / "B.java"}\n', encoding="utf-8")
        (self.code / "out").mkdir()
        r = self.javac("-encoding", "UTF-8", "-d", "out", "@args.txt")
        self.assertEqual(r.returncode, 0, r.stderr)
        [line] = self.runs()
        self.assertEqual(line["status"], "compiled")
        self.assertEqual([Path(f["file"]).name for f in line["files"]], ["A.java", "B.java"])

    def test_class_run_finds_source_through_bin_src(self):
        project = self.code / "project"
        src = self.project(project)
        r = self.run_java("-cp", project / "bin", "app.Main")
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (0, "hi", ""))
        r = self.run_java("-cp", project / "bin", "app.Boom")
        # The default behaviour is kept: same trace header, exit code 1.
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith('Exception in thread "main" java.lang.IllegalStateException: boom'),
                        r.stderr)
        ok, boom = self.runs()
        self.assertEqual((ok["status"], ok["error"], ok["source"]), ("success", None, "agent"))
        self.assertEqual(ok["file"], str(src / "Main.java"))
        self.assertEqual([Path(f["file"]).name for f in ok["files"]], ["Main.java", "Boom.java", "Helper.java"])
        self.assertEqual((boom["status"], boom["error"]), ("error", "IllegalStateException"))

    def test_maven_layout_finds_src_main_java(self):
        src = self.code / "mvn" / "src" / "main" / "java"
        src.mkdir(parents=True)
        (src / "Hello.java").write_text("public class Hello { public static void main(String[] a) {} }\n",
                                        encoding="utf-8")
        (self.code / "mvn" / "target" / "classes").mkdir(parents=True)
        self.assertEqual(self.javac("-d", self.code / "mvn" / "target" / "classes", src / "Hello.java",
                                    agent=False).returncode, 0)
        self.assertEqual(self.run_java("-cp", "mvn/target/classes", "Hello").returncode, 0)
        [line] = self.runs()
        self.assertEqual(line["file"], str(src / "Hello.java"))

    def test_class_without_source_or_class_file_not_logged(self):
        (self.code / "bin").mkdir()
        self.run_java("-cp", "bin", "app.Missing")
        self.assertEqual(self.runs(), [])

    @unittest.skipUnless(JAVA_MAJOR >= 11, "single-file source launch needs Java 11+")
    def test_source_launch(self):
        (self.code / "Hello.java").write_text(
            "public class Hello { public static void main(String[] a) { System.out.println(1); } }\n",
            encoding="utf-8")
        self.assertEqual(self.run_java("Hello.java").returncode, 0)
        [line] = self.runs()
        self.assertEqual((line["status"], line["file"]), ("success", str(self.code / "Hello.java")))

    @unittest.skipUnless(0 < JAVA_MAJOR < 11, "Java 11+ can launch source files")
    def test_source_launch_before_java_11_not_logged(self):
        (self.code / "Hello.java").write_text("public class Hello {}\n", encoding="utf-8")
        self.assertNotEqual(self.run_java("Hello.java").returncode, 0)  # "could not find main class"
        self.assertEqual(self.runs(), [])

    def test_excluded_folder_not_logged(self):
        project = self.code / "project"
        self.project(project)
        self.write_props(exclude=[str(project).upper() + "\\"])
        self.run_java("-cp", project / "bin", "app.Main")
        self.assertEqual(self.runs(), [])
        # A bare name (like the built-in node_modules, AppData...) excludes any folder of that name.
        lib = self.code / "node_modules" / "lib"
        self.project(lib)
        self.write_props(exclude=["node_modules"])
        self.run_java("-cp", lib / "bin", "app.Main")
        self.javac(lib / "src" / "app" / "Helper.java")
        self.assertEqual(self.runs(), [])

    def test_tracker_dir_excluded(self):
        project = self.code / "project"
        self.project(project)
        props = self.jar.with_name("agent.properties")
        with mock.patch.object(jpack.settings, "TRACKER_DIR", self.code):
            jpack.write_properties(props, {"exclude_folders": []}, self.data, builtin=False)
        self.run_java("-cp", project / "bin", "app.Main")
        self.assertEqual(self.runs(), [])

    def test_paths_with_spaces_quotes_unicode_are_valid_json(self):
        # Windows forbids '"' in folder names, so the quote is checked through json() below.
        project = self.code / "Ana María 'test' {x}"
        src = self.project(project)
        self.assertEqual(self.run_java("-cp", project / "bin", "app.Main").returncode, 0)
        [line] = self.runs()
        self.assertTrue(line["file"].endswith("Ana María 'test' {x}\\src\\app\\Main.java"), line["file"])
        self.assertEqual(line["file"], str(src / "Main.java"))

    def test_json_escaping(self):
        (self.code / "Check.java").write_text(
            "import java.nio.file.*;\n"
            "public class Check { public static void main(String[] a) throws Exception {\n"
            "  String s = \"q\\\" b\\\\ n\\n r\\r t\\t c\\u0001 \\u00e9\\u4e2d\";\n"
            "  Files.write(Paths.get(\"out.json\"), TrackerAgent.json(s).getBytes(\"UTF-8\")); } }\n",
            encoding="utf-8")
        self.assertEqual(self.javac("-cp", self.jar, "Check.java", agent=False).returncode, 0)
        r = subprocess.run([str(JAVA), "-cp", f"{self.jar}{os.pathsep}.", "Check"], cwd=self.code,
                           capture_output=True, text=True, timeout=60, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        raw = (self.code / "out.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(raw), 'q" b\\ n\n r\r t\t c\x01 é中')
        self.assertIn("\\u0001", raw)
        self.assertIn("é中", raw)

    def test_untracked_processes_get_nothing(self):
        # A -jar launch (like many tools) must run untouched and log nothing.
        jarred = self.code / "tool.jar"
        with zipfile.ZipFile(jarred, "w") as z:
            z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\n\r\n")
        self.run_java("-jar", jarred)
        self.assertEqual(self.runs(), [])

    def test_missing_properties_is_silent(self):
        self.jar.with_name("agent.properties").unlink()
        project = self.code / "project"
        self.project(project)
        r = self.run_java("-cp", project / "bin", "app.Main")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.runs(), [])

    def test_jar_manifest_and_rebuild_is_identical(self):
        with zipfile.ZipFile(self.jar) as z:
            self.assertEqual(z.read("META-INF/MANIFEST.MF").decode(),
                             "Manifest-Version: 1.0\r\nPremain-Class: TrackerAgent\r\n\r\n")
            self.assertIn("TrackerAgent.class", z.namelist())
        before = self.jar.read_bytes()
        jpack.build_agent(self.jar_dir)
        self.assertEqual(self.jar.read_bytes(), before)


class FindJavacTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jfind_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def fake_jdk(self, *parts):
        bin_dir = self.tmp.joinpath(*parts, "bin")
        bin_dir.mkdir(parents=True)
        (bin_dir / "javac.exe").write_text("")
        (bin_dir / "java.exe").write_text("")
        return bin_dir / "javac.exe"

    def test_path_first(self):
        with mock.patch.object(jpack.shutil, "which", return_value=r"C:\jdk\bin\javac.exe"):
            self.assertEqual(jpack.find_javac(), Path(r"C:\jdk\bin\javac.exe"))

    def test_java_home_then_newest_program_files_jdk(self):
        home = self.fake_jdk("home")
        self.fake_jdk("Java", "jdk1.8.0_511")
        newest = self.fake_jdk("Eclipse Adoptium", "jdk-17.0.9.9-hotspot")
        self.fake_jdk("Microsoft", "jdk-11.0.2")
        roots = [self.tmp / n for n in ("Java", "Eclipse Adoptium", "Microsoft", "Zulu")]
        with mock.patch.object(jpack.shutil, "which", return_value=None), \
                mock.patch.object(jpack, "JDK_ROOTS", roots):
            with mock.patch.dict(os.environ, {"JAVA_HOME": str(home.parent.parent)}):
                self.assertEqual(jpack.find_javac(), home)
            with mock.patch.dict(os.environ, {"JAVA_HOME": ""}):
                self.assertEqual(jpack.find_javac(), newest)
                self.assertEqual(jpack.java_for(newest), newest.with_name("java.exe"))
            with mock.patch.dict(os.environ, {"JAVA_HOME": ""}), mock.patch.object(jpack, "JDK_ROOTS", []):
                self.assertIsNone(jpack.find_javac())

    def test_version_key_orders_old_and_new_names(self):
        names = ["jdk-11.0.2", "jdk1.8.0_511", "jdk-21", "jdk-17.0.9.9-hotspot"]
        self.assertEqual(sorted(names, key=lambda n: jpack._version_key(Path(n))),
                         ["jdk1.8.0_511", "jdk-11.0.2", "jdk-17.0.9.9-hotspot", "jdk-21"])


class PackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jpack_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.jar = self.tmp / "agent" / "tracker-agent.jar"
        self.cfg = {"exclude_folders": [r"C:\Old Stuff"]}

    def fake_build(self, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "tracker-agent.jar").write_bytes(b"jar")
        return out_dir / "tracker-agent.jar"

    def install(self, self_test_result):
        pack = get_pack("java")
        with mock.patch.object(jpack.envvars, "user_env_add") as add, \
                mock.patch.object(jpack.envvars, "user_env_remove") as rem, \
                mock.patch.object(jpack, "find_javac", return_value=Path("javac.exe")), \
                mock.patch.object(jpack, "build_agent", side_effect=self.fake_build), \
                mock.patch.object(pack, "self_test", return_value=self_test_result) as st:
            result = pack.install_with_jar_path(self.jar, self.cfg, Path(r"D:\data"))
        return result, add, rem, st

    def test_install_refuses_space(self):
        pack = get_pack("java")
        with mock.patch.object(jpack.envvars, "user_env_add") as add:
            ok, msg = pack.install_with_jar_path(Path(r"C:\My Tools\tracker-agent.jar"), self.cfg, Path("D"))
        self.assertFalse(ok)
        self.assertIn("space", msg)
        add.assert_not_called()

    def test_install_sets_env_only_after_self_test(self):
        token = jpack.agent_token(self.jar)
        (ok, _), add, rem, st = self.install((False, "boom"))
        self.assertFalse(ok)
        add.assert_not_called()
        rem.assert_called_once_with("JAVA_TOOL_OPTIONS", token)
        self.assertEqual(st.call_args.kwargs["jar_path"], self.jar)
        result, add, rem, _ = self.install((True, "ok"))
        self.assertEqual(result, (True, "Java agent installed"))
        add.assert_called_once_with("JAVA_TOOL_OPTIONS", token)

    def test_install_writes_properties(self):
        self.install((True, "ok"))
        props = (self.jar.with_name("agent.properties")).read_text(encoding="utf-8")
        values = dict(line.split("=", 1) for line in props.splitlines())
        self.assertEqual(values["data_dir"], r"D:\\data")
        self.assertEqual(values["tracker_dir"], str(jpack.settings.TRACKER_DIR).replace("\\", "\\\\"))
        self.assertEqual(values["exclude"].split(";"),
                         list(jpack.BUILTIN_EXCLUDES) + [r"C:\\Old Stuff"])

    def test_install_without_javac(self):
        pack = get_pack("java")
        with mock.patch.object(jpack.envvars, "user_env_add") as add, \
                mock.patch.object(jpack, "find_javac", return_value=None):
            ok, msg = pack.install_with_jar_path(self.jar, self.cfg, Path("D"))
        self.assertEqual((ok, msg), (False, "javac not found: Java will use the Eclipse-build scan only. "
                                            "Install a JDK or set JAVA_HOME, then re-run setup."))
        add.assert_not_called()

    def test_install_build_failure_leaves_env_alone(self):
        pack = get_pack("java")
        with mock.patch.object(jpack.envvars, "user_env_add") as add, \
                mock.patch.object(jpack, "find_javac", return_value=Path("javac.exe")), \
                mock.patch.object(jpack, "build_agent", side_effect=RuntimeError("bad source")):
            ok, msg = pack.install_with_jar_path(self.jar, self.cfg, Path("D"))
        self.assertFalse(ok)
        self.assertIn("bad source", msg)
        add.assert_not_called()

    def test_install_uses_real_jar_path(self):
        pack = get_pack("java")
        with mock.patch.object(pack, "install_with_jar_path", return_value=(True, "x")) as core:
            pack.install(self.cfg, Path("D"))
        core.assert_called_once_with(jpack.JAR_PATH, self.cfg, Path("D"))
        self.assertEqual(jpack.JAR_PATH, jpack.PACK.dir / "agent" / "tracker-agent.jar")

    def test_uninstall_removes_token(self):
        with mock.patch.object(jpack.envvars, "user_env_remove", return_value=True) as rem:
            self.assertEqual(get_pack("java").uninstall(), "Java agent removed")
        rem.assert_called_once_with("JAVA_TOOL_OPTIONS", jpack.AGENT_TOKEN)

    def test_hook_installed_reads_user_env(self):
        pack = get_pack("java")
        with mock.patch.object(jpack.envvars, "get_user_env", return_value="-Xmx1g " + jpack.AGENT_TOKEN):
            self.assertTrue(pack.hook_installed())
        with mock.patch.object(jpack.envvars, "get_user_env", return_value="-Xmx1g"):
            self.assertFalse(pack.hook_installed())
        with mock.patch.object(jpack.envvars, "get_user_env", return_value=None):
            self.assertFalse(pack.hook_installed())

    def test_token_format(self):
        self.assertEqual(jpack.AGENT_TOKEN, "-javaagent:" + str(jpack.JAR_PATH).replace("\\", "/"))
        self.assertNotIn(" ", jpack.AGENT_TOKEN)


@NEEDS_JDK
class SelfTestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jself_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.jar = jpack.build_agent(self.tmp)

    def test_self_test_passes_through_java_tool_options(self):
        live = self.jar.with_name("agent.properties")
        live.write_text("data_dir=untouched\n", encoding="utf-8")
        with mock.patch.object(jpack.subprocess, "run", wraps=subprocess.run) as run:
            ok, msg = get_pack("java").self_test({"exclude_folders": []}, jar_path=self.jar)
        self.assertTrue(ok, msg)
        java_call = run.call_args_list[-1]
        self.assertNotIn("-javaagent", " ".join(java_call.args[0]))
        self.assertEqual(java_call.kwargs["env"]["JAVA_TOOL_OPTIONS"], jpack.agent_token(self.jar))
        self.assertEqual(live.read_text(encoding="utf-8"), "data_dir=untouched\n")

    def test_broken_token_fails_and_install_skips_env(self):
        missing = self.tmp / "gone" / "tracker-agent.jar"
        ok, msg = get_pack("java").self_test({}, jar_path=missing)
        self.assertFalse(ok)
        pack = get_pack("java")
        with mock.patch.object(jpack, "agent_token", return_value=f"-javaagent:{missing}"), \
                mock.patch.object(jpack.envvars, "user_env_add") as add, \
                mock.patch.object(jpack.envvars, "user_env_remove"):
            ok, msg = pack.install_with_jar_path(self.tmp / "tracker-agent.jar", {"exclude_folders": []},
                                                 self.tmp / "data")
        self.assertFalse(ok, msg)
        add.assert_not_called()
