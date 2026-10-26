// Learning Tracker: Java run logger.
//
// setup.py adds -javaagent:<tracker-agent.jar> to the user's JAVA_TOOL_OPTIONS, so
// this premain runs inside EVERY Java program on the PC (Eclipse, Gradle, the VS
// Code language server...). It therefore stays tiny: it looks at the command line,
// and only for a command-line javac compile or a run of a learner's own .java code
// does it read its settings and add a shutdown hook. It then records time, file(s),
// status, error type and duration plus snapshots of the code in
// <data_dir>/java/runs.jsonl. It prints nothing, and every step sits inside
// catch (Throwable): it must never break a program.
// Settings: agent.properties beside the jar (or the file named by JAVATRACKER_PROPS).
// Java 8 source only. To stop logging run: python tracker\setup.py --uninstall

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.ProtectionDomain;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Properties;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class TrackerAgent {
    private static final Charset UTF8 = Charset.forName("UTF-8");
    private static final String[] IGNORED = {"org.eclipse.", "org.gradle.", "org.codehaus.plexus.classworlds"};
    // javac options whose value is the next argument (so the value is never taken for a source file).
    private static final Set<String> VALUE_OPTIONS = new HashSet<String>(Arrays.asList(
            "-cp", "-classpath", "--class-path", "-sourcepath", "--source-path", "-encoding",
            "--release", "-source", "--source", "-target", "--target", "-processorpath",
            "--processor-path", "-processor", "-s", "-h", "-bootclasspath", "-extdirs",
            "-endorseddirs", "--module-path", "-p", "--module-source-path", "--add-modules",
            "--limit-modules", "--upgrade-module-path", "--system", "-Xmaxerrs", "-Xmaxwarns"));

    static volatile String error;      // simple name of the first uncaught exception (run mode)
    static volatile boolean started;   // source launch: the learner's code got past compiling
    static boolean watchStart;
    static long startMillis;
    static String dataDir;
    static List<String> excludes = new ArrayList<String>();

    public static void premain(String args, Instrumentation inst) {
        try {
            start(inst);
        } catch (Throwable t) {
            // never break the program
        }
    }

    static void start(Instrumentation inst) throws Exception {
        startMillis = System.currentTimeMillis();
        String cmd = System.getProperty("sun.java.command", "");
        String mode = mode(cmd, javaVersion());
        // Settings are read only once a learner's source file has been found.
        if (mode.equals("compile")) {
            List<String> tokens = split(cmd);
            compileMode(tokens.subList(1, tokens.size()));
        } else if (mode.startsWith("source:")) {
            if (sourceRun(split(cmd), Integer.parseInt(mode.substring(7))) && inst != null) {
                // The launcher reports a compile error with System.exit(1): only a class defined by
                // its in-memory loader shows the learner's code really started.
                watchStart = true;
                inst.addTransformer(new Starter(inst));
            }
        } else if (mode.startsWith("class:")) {
            String main = mode.substring(6);
            String first = split(cmd).get(0);
            int slash = first.indexOf('/');
            classRun(main, slash > 0 && !first.equals(main) ? first.substring(0, slash) : null);
        }
    }

    /**
     * What this JVM is, from sun.java.command alone (no file-system work): "compile",
     * "source:<index of the file token>", "class:<main class>" or "none".
     */
    static String mode(String cmd, int javaVersion) {
        List<String> tokens = split(cmd);
        if (tokens.isEmpty()) {
            return "none";  // launched through JNI (e.g. eclipse.exe): not a learner's program
        }
        String first = tokens.get(0);
        String main = stripModule(first);
        boolean sourceLaunch = javaVersion >= 11;  // `java Foo.java` only exists from Java 11
        if (main.equals("com.sun.tools.javac.Main")) {
            return "compile";
        }
        if (main.startsWith("com.sun.tools.javac.launcher.")) {
            // Java 11-21: ...launcher.Main <file>; 22+: ...launcher.SourceLauncher <file>.
            return sourceLaunch && tokens.size() > 1 ? "source:1" : "none";
        }
        if (ignored(main)) {
            return "none";
        }
        if (first.toLowerCase(Locale.ROOT).endsWith(".java")) {
            return sourceLaunch ? "source:0" : "none";  // before Java 11 the launch just fails
        }
        // A .java path with spaces arrives split up; only an absolute path is worth rejoining.
        if (sourceLaunch && (first.indexOf(':') >= 0 || first.startsWith("\\"))
                && cmd.toLowerCase(Locale.ROOT).contains(".java")) {
            return "source:0";
        }
        return "class:" + main;
    }

    // ---------- modes ----------

    static void compileMode(List<String> args) throws Exception {
        List<String> expanded = new ArrayList<String>();
        for (String a : args) {
            if (a.startsWith("@") && a.length() > 1) {
                expanded.addAll(readArgFile(new File(a.substring(1))));
            } else {
                expanded.add(a);
            }
        }
        File outDir = null;
        List<File> sources = new ArrayList<File>();
        for (int i = 0; i < expanded.size(); i++) {
            String a = expanded.get(i);
            if (a.equals("-d") && i + 1 < expanded.size()) {
                outDir = new File(expanded.get(++i)).getAbsoluteFile();
            } else if (VALUE_OPTIONS.contains(a)) {
                i++;
            } else if (a.startsWith("-")) {
                continue;
            } else {
                int end = javaPathEnd(expanded, i);
                if (end > 0) {
                    sources.add(absolute(join(expanded, i, end)));
                    i = end - 1;
                }
            }
        }
        if (sources.isEmpty() || !loadSettings()) {
            return;
        }
        for (int i = sources.size() - 1; i >= 0; i--) {
            if (excluded(sources.get(i))) {
                sources.remove(i);
            }
        }
        if (sources.isEmpty()) {
            return;
        }
        List<File> classes = new ArrayList<File>();
        for (File src : sources) {
            String name = src.getName().substring(0, src.getName().length() - 5) + ".class";
            if (outDir == null) {
                classes.add(new File(src.getParentFile(), name));  // javac writes beside the source
            } else {
                String pkg = packageOf(src);
                File dir = pkg.isEmpty() ? outDir : new File(outDir, pkg.replace('.', File.separatorChar));
                classes.add(new File(dir, name));
            }
        }
        addHook(new Entry("javac", sources, classes));
    }

    static void classRun(String main, String module) throws Exception {
        String rel = main.replace('.', '/');
        List<String> dirs = new ArrayList<String>();
        for (String part : System.getProperty("java.class.path", ".").split(File.pathSeparator, -1)) {
            dirs.add(part.isEmpty() ? "." : part);
        }
        // `java -m mod/pkg.Main`: an exploded module is the module-path folder or a folder in it.
        for (String part : System.getProperty("jdk.module.path", "").split(File.pathSeparator)) {
            if (!part.isEmpty()) {
                dirs.add(part);
                if (module != null) {
                    dirs.add(part + File.separator + module);
                }
            }
        }
        for (String part : dirs) {
            String low = part.toLowerCase(Locale.ROOT);
            // This runs in every JVM, so jars (often hundreds of them) are skipped by name alone.
            if (low.endsWith(".jar") || low.endsWith(".zip") || low.endsWith("*")) {
                continue;
            }
            // Only the folder that really holds the compiled class (otherwise the launch fails).
            if (!new File(part, rel + ".class").isFile()) {
                continue;
            }
            File dir = absolute(part);
            List<File> candidates = new ArrayList<File>();
            candidates.add(dir);
            candidates.add(new File(dir, "../src"));
            if (dir.getPath().replace('\\', '/').toLowerCase(Locale.ROOT).endsWith("target/classes")) {
                candidates.add(new File(dir, "../../src/main/java"));
            }
            candidates.add(new File(dir, "../src/main/java"));
            for (File c : candidates) {
                File src = normalize(new File(c, rel + ".java"));
                if (src.isFile()) {
                    if (loadSettings() && !excluded(src)) {
                        startRun(src);
                    }
                    return;
                }
            }
        }
    }

    static boolean sourceRun(List<String> tokens, int from) throws Exception {
        if (from >= tokens.size()) {
            return false;
        }
        int end = javaPathEnd(tokens, from);
        File src = absolute(end > 0 ? join(tokens, from, end) : tokens.get(from));
        if (src.isFile() && loadSettings() && !excluded(src)) {
            startRun(src);
            return true;
        }
        return false;
    }

    static void startRun(File src) {
        List<File> files = new ArrayList<File>();
        files.add(src);
        File[] siblings = src.getParentFile().listFiles();
        if (siblings != null) {
            Arrays.sort(siblings);
            for (File f : siblings) {
                if (f.isFile() && f.getName().toLowerCase(Locale.ROOT).endsWith(".java")
                        && !f.equals(src) && !excluded(f)) {
                    files.add(f);
                }
            }
        }
        Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler(new Handler(previous));
        addHook(new Entry("agent", files, null));
    }

    static void addHook(Entry entry) {
        Runtime.getRuntime().addShutdownHook(new Thread(new Hook(entry), "learning-tracker"));
    }

    /** Records the exception's name, then behaves exactly like the handler it replaced. */
    static final class Handler implements Thread.UncaughtExceptionHandler {
        private final Thread.UncaughtExceptionHandler previous;

        Handler(Thread.UncaughtExceptionHandler previous) {
            this.previous = previous;
        }

        public void uncaughtException(Thread t, Throwable e) {
            try {
                if (error == null) {
                    error = e.getClass().getSimpleName();
                }
            } catch (Throwable ignored) {
                // keep going: the trace must still be printed
            }
            if (previous != null) {
                previous.uncaughtException(t, e);
            } else if (!"java.lang.ThreadDeath".equals(e.getClass().getName())) {
                // (By name: ThreadDeath is deprecated for removal in newer JDKs.)
                // What ThreadGroup.uncaughtException prints when no handler is set.
                System.err.print("Exception in thread \"" + t.getName() + "\" ");
                e.printStackTrace(System.err);
            }
        }
    }

    /**
     * Installed only in a tracked source launch: notes the first class defined by a loader other
     * than the boot, platform and application ones (the launcher's in-memory loader), then removes
     * itself. It never changes a class (returns null).
     */
    static final class Starter implements ClassFileTransformer {
        private final Instrumentation inst;
        private final ClassLoader app = ClassLoader.getSystemClassLoader();
        private final ClassLoader platform = app == null ? null : app.getParent();

        Starter(Instrumentation inst) {
            this.inst = inst;
        }

        public byte[] transform(ClassLoader loader, String className, Class<?> redefined,
                                ProtectionDomain domain, byte[] bytes) {
            try {
                if (!started && loader != null && loader != app && loader != platform
                        && !loader.getClass().getName().endsWith("DelegatingClassLoader")) {
                    started = true;
                    inst.removeTransformer(this);
                }
            } catch (Throwable t) {
                // never break class loading
            }
            return null;
        }
    }

    /** The shutdown hook: does the work in a daemon thread and gives up after 2 seconds. */
    static final class Hook implements Runnable {
        private final Entry entry;

        Hook(Entry entry) {
            this.entry = entry;
        }

        public void run() {
            try {
                Thread worker = new Thread(entry, "learning-tracker-writer");
                worker.setDaemon(true);
                worker.start();
                worker.join(2000);
            } catch (Throwable t) {
                // never block or break the JVM's exit
            }
        }
    }

    /** One run-log line, written when the JVM exits. */
    static final class Entry implements Runnable {
        private final String source;
        private final List<File> files;
        private final List<File> classes;   // compile mode only

        Entry(String source, List<File> files, List<File> classes) {
            this.source = source;
            this.files = files;
            this.classes = classes;
        }

        public void run() {
            try {
                write();
            } catch (Throwable t) {
                // never break the program
            }
        }

        void write() throws Exception {
            String status;
            String err = null;
            String errorCount = "null";
            if (classes != null) {
                // Coarse file systems keep whole seconds, so compare against the start second.
                long since = startMillis - startMillis % 1000;
                int bad = 0;
                for (File c : classes) {
                    if (!c.isFile() || c.lastModified() < since) {
                        bad++;
                    }
                }
                status = bad == 0 ? "compiled" : "compile_error";
                if (bad > 0) {
                    errorCount = String.valueOf(bad);
                }
            } else {
                err = error;
                status = err == null ? "success" : "error";
                if (watchStart && !started) {
                    status = "compile_error";  // the source launch never got past compiling
                    err = null;
                }
            }
            double duration = (System.currentTimeMillis() - startMillis) / 1000.0;

            File dir = new File(dataDir, "java");
            File snaps = new File(dir, "snapshots");
            snaps.mkdirs();
            StringBuilder list = new StringBuilder();
            String firstFile = null;
            for (File f : files) {
                byte[] bytes;
                try {
                    bytes = Files.readAllBytes(f.toPath());
                } catch (Exception e) {
                    continue;  // deleted or locked meanwhile
                }
                String sha = sha16(bytes);
                File snap = new File(snaps, sha + ".java");
                if (!snap.exists()) {
                    Files.write(snap.toPath(), bytes);
                }
                if (firstFile == null) {
                    firstFile = f.getPath();
                } else {
                    list.append(", ");
                }
                list.append("{\"file\": ").append(json(f.getPath()))
                        .append(", \"sha\": ").append(json(sha)).append("}");
            }
            if (firstFile == null) {
                return;
            }
            String line = "{\"time\": " + json(LocalDateTime.now().withNano(0).format(DateTimeFormatter.ISO_LOCAL_DATE_TIME))
                    + ", \"file\": " + json(firstFile)
                    + ", \"status\": " + json(status)
                    + ", \"error\": " + (err == null ? "null" : json(err))
                    + ", \"error_count\": " + errorCount
                    + ", \"duration\": " + String.format(Locale.ROOT, "%.2f", duration)
                    + ", \"source\": " + json(source)
                    + ", \"files\": [" + list + "]}\n";
            OutputStream out = new FileOutputStream(new File(dir, "runs.jsonl"), true);
            try {
                out.write(line.getBytes(UTF8));  // one write, so concurrent JVMs don't interleave a line
            } finally {
                out.close();
            }
        }
    }

    // ---------- settings and exclusions ----------

    static boolean loadSettings() {
        try {
            String env = System.getenv("JAVATRACKER_PROPS");
            File file;
            if (env != null && !env.isEmpty()) {
                file = new File(env);
            } else {
                File jar = new File(TrackerAgent.class.getProtectionDomain().getCodeSource().getLocation().toURI());
                file = new File(jar.getParentFile(), "agent.properties");
            }
            Properties props = new Properties();
            InputStream in = new FileInputStream(file);
            try {
                props.load(new InputStreamReader(in, UTF8));
            } finally {
                in.close();
            }
            dataDir = props.getProperty("data_dir", "");
            if (dataDir.isEmpty()) {
                return false;
            }
            excludes.clear();
            for (String e : props.getProperty("exclude", "").split(";")) {
                addExclude(e);
            }
            addExclude(props.getProperty("tracker_dir", ""));
            return true;
        } catch (Throwable t) {
            return false;  // no settings: stay silent
        }
    }

    static void addExclude(String e) {
        String s = e.trim().replace('/', '\\').toLowerCase(Locale.ROOT);
        while (s.endsWith("\\")) {
            s = s.substring(0, s.length() - 1);
        }
        if (!s.isEmpty()) {
            excludes.add(s);
        }
    }

    /** A folder path excludes everything under it; a bare name (AppData, .m2...) excludes any folder of that name. */
    static boolean excluded(File f) {
        String p = normalize(f).getPath().replace('/', '\\').toLowerCase(Locale.ROOT);
        for (String e : excludes) {
            boolean isPath = e.indexOf('\\') >= 0 || e.indexOf(':') >= 0;
            if (isPath ? (p.equals(e) || p.startsWith(e + "\\")) : p.contains("\\" + e + "\\")) {
                return true;
            }
        }
        return false;
    }

    // ---------- helpers ----------

    static boolean ignored(String main) {
        if (main.toLowerCase(Locale.ROOT).endsWith(".jar")) {
            return true;
        }
        for (String prefix : IGNORED) {
            if (main.startsWith(prefix)) {
                return true;
            }
        }
        return false;
    }

    /** "jdk.compiler/com.sun.tools.javac.Main" -> "com.sun.tools.javac.Main" (Java 9+ module launches). */
    static String stripModule(String token) {
        int slash = token.indexOf('/');
        if (slash < 0 || token.indexOf('\\') >= 0 || token.indexOf(':') >= 0
                || token.toLowerCase(Locale.ROOT).endsWith(".java")) {
            return token;
        }
        return token.substring(slash + 1);
    }

    static int javaVersion() {
        String v = System.getProperty("java.specification.version", "1.8");
        if (v.startsWith("1.")) {
            v = v.substring(2);
        }
        int dot = v.indexOf('.');
        try {
            return Integer.parseInt(dot < 0 ? v : v.substring(0, dot));
        } catch (NumberFormatException e) {
            return 8;
        }
    }

    /** Splits on whitespace outside double quotes; the quotes are dropped. */
    static List<String> split(String s) {
        List<String> out = new ArrayList<String>();
        StringBuilder cur = new StringBuilder();
        boolean quoted = false;
        boolean any = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"') {
                quoted = !quoted;
                any = true;
            } else if (Character.isWhitespace(c) && !quoted) {
                if (any) {
                    out.add(cur.toString());
                    cur.setLength(0);
                    any = false;
                }
            } else {
                cur.append(c);
                any = true;
            }
        }
        if (any) {
            out.add(cur.toString());
        }
        return out;
    }

    /**
     * sun.java.command joins arguments with plain spaces, so "C:\My Code\A.java" arrives as two
     * tokens. Returns the end index of the shortest run of tokens from `from` that forms an
     * existing .java file (or a single .java token), else -1.
     */
    static int javaPathEnd(List<String> tokens, int from) {
        for (int end = from + 1; end <= tokens.size(); end++) {
            String path = join(tokens, from, end);
            if (path.toLowerCase(Locale.ROOT).endsWith(".java")) {
                if (end == from + 1 || absolute(path).isFile()) {
                    return end;
                }
            }
        }
        return -1;
    }

    static String join(List<String> tokens, int from, int end) {
        StringBuilder b = new StringBuilder(tokens.get(from));
        for (int i = from + 1; i < end; i++) {
            b.append(' ').append(tokens.get(i));
        }
        return b.toString();
    }

    /**
     * javac @argfile, read like javac does: arguments split on whitespace, "..." or '...' group
     * one argument (quotes stripped, backslash escapes inside them), # starts a comment.
     */
    static List<String> readArgFile(File file) throws Exception {
        String s = new String(Files.readAllBytes(file.toPath()), UTF8);
        List<String> out = new ArrayList<String>();
        StringBuilder cur = new StringBuilder();
        boolean any = false;
        char quote = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (quote != 0) {
                if (c == quote) {
                    quote = 0;
                } else if (c == '\\' && i + 1 < s.length()) {
                    char n = s.charAt(++i);
                    cur.append(n == 'n' ? '\n' : n == 't' ? '\t' : n == 'r' ? '\r' : n);
                } else {
                    cur.append(c);
                }
            } else if (c == '"' || c == '\'') {
                quote = c;
                any = true;
            } else if (c == '#') {
                while (i + 1 < s.length() && s.charAt(i + 1) != '\n') {
                    i++;
                }
            } else if (Character.isWhitespace(c)) {
                if (any) {
                    out.add(cur.toString());
                    cur.setLength(0);
                    any = false;
                }
            } else {
                cur.append(c);
                any = true;
            }
        }
        if (any) {
            out.add(cur.toString());
        }
        return out;
    }

    static String packageOf(File src) {
        try {
            // Compiled here, not in a static field: this class loads in every JVM.
            Pattern pkg = Pattern.compile("^\\s*package\\s+([\\w.]+)\\s*;", Pattern.MULTILINE);
            Matcher m = pkg.matcher(new String(Files.readAllBytes(src.toPath()), UTF8));
            return m.find() ? m.group(1) : "";
        } catch (Exception e) {
            return "";
        }
    }

    static File absolute(String path) {
        File f = new File(path);
        if (!f.isAbsolute()) {
            f = new File(System.getProperty("user.dir", "."), path);
        }
        return normalize(f);
    }

    static File normalize(File f) {
        return f.getAbsoluteFile().toPath().normalize().toFile();
    }

    static String sha16(byte[] bytes) throws Exception {
        byte[] d = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < 8; i++) {
            b.append(String.format("%02x", d[i] & 0xff));
        }
        return b.toString();
    }

    /** A JSON string literal; non-ASCII is kept as is because the file is UTF-8. */
    static String json(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': b.append("\\\\"); break;
                case '"': b.append("\\\""); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
            }
        }
        return b.append('"').toString();
    }
}
