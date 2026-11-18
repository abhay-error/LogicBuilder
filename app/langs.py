"""Multi-language support (LLD §6 CodeRunner strategies).

Languages: Python, JavaScript, TypeScript, Java, C++, Go, C#.
For problems, starter code and a test driver are GENERATED from a language-neutral signature
(content/signatures.py). The driver embeds the test inputs, calls the learner's function, and prints
one marker line per test (`<token> T <i> <json>` or `<token> E <i> <message>`); we compare in Python.
A random per-run token means learner prints can't forge results.

Toolchains are detected at runtime; missing ones are reported with an install hint instead of failing.
Local mode runs code with your own user rights (like running it yourself). A public product must use
containers (HLD §11): this module is the seam where a remote judge would plug in.
"""
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import sandbox

IS_WIN = os.name == "nt"
MAX_OUT = 200_000          # bytes of program output we keep
MAX_FILE = 5_000_000       # kill programs that print more than this
COMPILE_TIMEOUT = 120      # dotnet's first build can be slow


# ------------------------------------------------------------------ naming and literals
def camel(name):
    p = name.split("_")
    return p[0] + "".join(x[:1].upper() + x[1:] for x in p[1:])


def pascal(name):
    return "".join(x[:1].upper() + x[1:] for x in name.split("_"))


TYPES = {
    "typescript": {"int": "number", "long": "number", "str": "string", "bool": "boolean", "list[int]": "number[]", "list[str]": "string[]"},
    "java": {"int": "int", "long": "long", "str": "String", "bool": "boolean", "list[int]": "int[]", "list[str]": "String[]"},
    "cpp": {"int": "int", "long": "long long", "str": "string", "bool": "bool", "list[int]": "vector<int>&", "list[str]": "vector<string>&"},
    "go": {"int": "int", "long": "int", "str": "string", "bool": "bool", "list[int]": "[]int", "list[str]": "[]string"},
    "csharp": {"int": "int", "long": "long", "str": "string", "bool": "bool", "list[int]": "int[]", "list[str]": "string[]"},
}
DEFAULTS = {
    "typescript": {"int": "0", "long": "0", "str": '""', "bool": "false", "list[int]": "[]", "list[str]": "[]"},
    "java": {"int": "0", "long": "0", "str": '""', "bool": "false", "list[int]": "null", "list[str]": "null"},
    "go": {"int": "0", "long": "0", "str": '""', "bool": "false", "list[int]": "nil", "list[str]": "nil"},
}


def lit(lang, t, v):
    """Source literal for value v of neutral type t."""
    if t in ("int", "long"):
        return str(v)
    if t == "bool":
        return "true" if v else "false"
    if t == "str":
        return json.dumps(v)  # JSON string literals are valid in every language here (ASCII content)
    items = [json.dumps(x) if t == "list[str]" else str(x) for x in v]
    inner = ",".join(items)
    base = "int" if t == "list[int]" else "string"
    if lang in ("javascript", "typescript"):
        return f"[{inner}]"
    if lang in ("java", "csharp"):
        return f"new {'int' if base == 'int' else ('String' if lang == 'java' else 'string')}[]{{{inner}}}"
    if lang == "go":
        return f"[]{base}{{{inner}}}"
    return f"{{{inner}}}"  # cpp: used as initializer of a declared vector


# ------------------------------------------------------------------ language definitions
class Lang:
    id = label = ext = ""
    visualize = False

    def fn_name(self, py):
        return camel(py)

    # to override
    def starter(self, args, ret, name): raise NotImplementedError
    def program_template(self): raise NotImplementedError
    def program_files(self, code): raise NotImplementedError
    def test_files(self, code, args, ret, name, tests, tk): raise NotImplementedError
    def build(self, tc, wd, files): return []
    def run_cmd(self, tc, wd, files): raise NotImplementedError
    def env(self): return None


class Python(Lang):
    id, label, ext, visualize = "python", "Python", "py", True

    def fn_name(self, py): return py

    def starter(self, args, ret, name): return None  # python starters come from the problem itself

    def program_template(self):
        return "numbers = [5, 3, 8]\ntotal = 0\nfor n in numbers:\n    total += n\nprint(total)\n"


class JavaScript(Lang):
    id, label, ext = "javascript", "JavaScript", "js"
    DRIVER = r'''
;(function () {
  const __tk = "__TK__";
  const __tests = __TESTS__;
  for (let i = 0; i < __tests.length; i++) {
    try {
      const r = __CALL__;
      console.log(__tk + " T " + i + " " + JSON.stringify(r === undefined ? null : r));
    } catch (e) {
      console.log(__tk + " E " + i + " " + String(e && e.message || e).replace(/\n/g, " "));
    }
  }
})();
'''

    def starter(self, args, ret, name):
        return f"function {name}({', '.join(a for a, _ in args)}) {{\n    // your code here\n}}\n"

    def program_template(self):
        return "const nums = [5, 3, 8];\nlet total = 0;\nfor (const n of nums) {\n    total += n;\n}\nconsole.log(total);\n"

    def program_files(self, code): return {"main.js": code}

    def _driver(self, name, tests, tk, cast=""):
        tj = json.dumps([t["input"] for t in tests])
        call = f"({name}{cast})(...__tests[i])"
        return self.DRIVER.replace("__TK__", tk).replace("__TESTS__", tj).replace("__CALL__", call)

    def test_files(self, code, args, ret, name, tests, tk):
        return {"main.js": code + "\n" + self._driver(name, tests, tk)}

    def build(self, tc, wd, files):
        return [[tc["node"], "--check", "main.js"]]  # report syntax errors as compile errors

    def run_cmd(self, tc, wd, files): return [tc["node"], "main.js"]


class TypeScript(JavaScript):
    id, label, ext = "typescript", "TypeScript", "ts"

    def starter(self, args, ret, name):
        T, D = TYPES["typescript"], DEFAULTS["typescript"]
        ps = ", ".join(f"{a}: {T[t]}" for a, t in args)
        return f"function {name}({ps}): {T[ret]} {{\n    // your code here\n    return {D[ret]};\n}}\n"

    def program_template(self):
        return "const nums: number[] = [5, 3, 8];\nlet total: number = 0;\nfor (const n of nums) {\n    total += n;\n}\nconsole.log(total);\n"

    def program_files(self, code): return {"main.ts": code}

    def test_files(self, code, args, ret, name, tests, tk):
        d = self._driver(name, tests, tk, cast=" as any").replace("const __tests =", "const __tests: any[][] =")
        return {"main.ts": code + "\n" + d}

    def build(self, tc, wd, files):
        if tc.get("mode") == "tsc":
            return [[tc["tsc"], "--target", "es2020", "--module", "commonjs", "--outDir", ".", "main.ts"]]
        return []  # syntax errors surface when Node strips the types; run() maps them to compile errors

    def run_cmd(self, tc, wd, files):
        if tc.get("mode") == "tsc":
            return [tc["node"], "main.js"]
        return [tc["node"], "--experimental-strip-types", "--no-warnings", "main.ts"]


class Java(Lang):
    id, label, ext = "java", "Java", "java"
    DRIVER = r'''
import java.util.*;

public class Main {
    static final String TK = "__TK__";

    static String esc(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 32) b.append(String.format("\\u%04x", (int) c)); else b.append(c);
            }
        }
        return b.append('"').toString();
    }

    // Java limits a method to 64KB of bytecode, so huge regular lists are built, not written out.
    static int[] rng(int start, int step, int n) {
        int[] a = new int[n];
        for (int i = 0; i < n; i++) a[i] = start + i * step;
        return a;
    }

    static String fmt(Object o) {
        if (o == null) return "null";
        if (o instanceof String) return esc((String) o);
        if (o instanceof int[]) {
            int[] a = (int[]) o;
            StringBuilder b = new StringBuilder("[");
            for (int i = 0; i < a.length; i++) { if (i > 0) b.append(','); b.append(a[i]); }
            return b.append(']').toString();
        }
        if (o instanceof String[]) {
            String[] a = (String[]) o;
            StringBuilder b = new StringBuilder("[");
            for (int i = 0; i < a.length; i++) { if (i > 0) b.append(','); b.append(a[i] == null ? "null" : esc(a[i])); }
            return b.append(']').toString();
        }
        return String.valueOf(o);
    }
__METHODS__
    public static void main(String[] args) {
        Solution s = new Solution();
__CALLS__
    }
}
'''

    def starter(self, args, ret, name):
        T, D = TYPES["java"], DEFAULTS["java"]
        ps = ", ".join(f"{T[t]} {a}" for a, t in args)
        return f"import java.util.*;\n\nclass Solution {{\n    public {T[ret]} {name}({ps}) {{\n        // your code here\n        return {D[ret]};\n    }}\n}}\n"

    def program_template(self):
        return ("public class Main {\n    public static void main(String[] args) {\n        int[] nums = {5, 3, 8};\n        int total = 0;\n"
                "        for (int n : nums) {\n            total += n;\n        }\n        System.out.println(total);\n    }\n}\n")

    def program_files(self, code): return {"Main.java": code}

    def test_files(self, code, args, ret, name, tests, tk):
        methods, calls = [], []
        for i, t in enumerate(tests):
            a = ", ".join(self._jlit(ty, v) for (_, ty), v in zip(args, t["input"]))
            methods.append(f"    static void t{i}(Solution s) {{\n        Object r = s.{name}({a});\n        System.out.println(TK + \" T {i} \" + fmt(r));\n    }}\n")
            calls.append(f"        try {{ t{i}(s); }} catch (Throwable e) {{ System.out.println(TK + \" E {i} \" + String.valueOf(e).replace(\"\\n\", \" \")); }}")
        drv = self.DRIVER.replace("__TK__", tk).replace("__METHODS__", "\n".join(methods)).replace("__CALLS__", "\n".join(calls))
        return {"Solution.java": code, "Main.java": drv}

    @staticmethod
    def _jlit(ty, v):
        if ty == "list[int]" and len(v) > 1000:
            d = v[1] - v[0]
            if all(v[k + 1] - v[k] == d for k in range(len(v) - 1)):
                return f"rng({v[0]}, {d}, {len(v)})"
            if len(v) > 4000:
                raise ValueError("list too large for the Java driver")
        return lit("java", ty, v)

    def build(self, tc, wd, files):
        return [[tc["javac"], "-encoding", "UTF-8", "-d", ".", *sorted(files)]]

    def run_cmd(self, tc, wd, files): return [tc["java"], "-Xmx256m", "-Xss16m", "-cp", ".", "Main"]


class Cpp(Lang):
    id, label, ext = "cpp", "C++", "cpp"
    HEAD = r'''
#include <algorithm>
#include <climits>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <map>
#include <numeric>
#include <queue>
#include <set>
#include <sstream>
#include <stack>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
using namespace std;
'''
    DRIVER = r'''
#include "solution.h"

static const char* TK = "__TK__";

static string esc(const string& s) {
    string o = "\"";
    for (unsigned char c : s) {
        if (c == '"') o += "\\\"";
        else if (c == '\\') o += "\\\\";
        else if (c == '\n') o += "\\n";
        else if (c == '\r') o += "\\r";
        else if (c == '\t') o += "\\t";
        else if (c < 32) { char b[8]; snprintf(b, sizeof b, "\\u%04x", c); o += b; }
        else o += (char)c;
    }
    return o + "\"";
}
static string fmt(bool v) { return v ? "true" : "false"; }
static string fmt(int v) { return to_string(v); }
static string fmt(long long v) { return to_string(v); }
static string fmt(const string& s) { return esc(s); }
static string fmt(const vector<int>& v) {
    string o = "[";
    for (size_t i = 0; i < v.size(); i++) { if (i) o += ","; o += to_string(v[i]); }
    return o + "]";
}
static string fmt(const vector<string>& v) {
    string o = "[";
    for (size_t i = 0; i < v.size(); i++) { if (i) o += ","; o += esc(v[i]); }
    return o + "]";
}
__METHODS__
int main() {
    Solution s;
__CALLS__
    return 0;
}
'''

    def starter(self, args, ret, name):
        T = TYPES["cpp"]
        ps = ", ".join(f"{T[t]} {a}" for a, t in args)
        return ("// vector, string, unordered_map, algorithm, etc. are already included for you.\nclass Solution {\npublic:\n"
                f"    {T[ret].rstrip('&')} {name}({ps}) {{\n        // your code here\n        return {{}};\n    }}\n}};\n")

    def program_template(self):
        return (self.HEAD.strip() + "\n\nint main() {\n    vector<int> nums = {5, 3, 8};\n    int total = 0;\n    for (int n : nums) {\n        total += n;\n    }\n"
                "    cout << total << endl;\n    return 0;\n}\n")

    def program_files(self, code): return {"main.cpp": code}

    def test_files(self, code, args, ret, name, tests, tk):
        methods, calls = [], []
        for i, t in enumerate(tests):
            decl = []
            for k, ((an, ty), v) in enumerate(zip(args, t["input"])):
                ct = {"int": "int", "str": "string", "list[int]": "vector<int>", "list[str]": "vector<string>"}[ty]
                decl.append(f"    {ct} a{k} = {lit('cpp', ty, v)};")
            names = ", ".join(f"a{k}" for k in range(len(args)))
            methods.append(f"static void t{i}(Solution& s) {{\n" + "\n".join(decl) + f"\n    auto r = s.{name}({names});\n    cout << TK << \" T {i} \" << fmt(r) << endl;\n}}\n")
            calls.append(f"    try {{ t{i}(s); }} catch (const exception& e) {{ cout << TK << \" E {i} \" << e.what() << endl; }} catch (...) {{ cout << TK << \" E {i} exception\" << endl; }}")
        drv = self.DRIVER.replace("__TK__", tk).replace("__METHODS__", "\n".join(methods)).replace("__CALLS__", "\n".join(calls))
        return {"solution.h": code, "main.cpp": self.HEAD + drv}

    def build(self, tc, wd, files):
        return [[tc["cxx"], "-std=c++17", "-O2", "-o", "prog", "main.cpp"]]

    def run_cmd(self, tc, wd, files): return [str(Path(wd) / ("prog.exe" if IS_WIN else "prog"))]


class Go(Lang):
    id, label, ext = "go", "Go", "go"
    DRIVER = r'''
package main

import (
	"encoding/json"
	"fmt"
	"reflect"
)

const tk = "__TK__"

func toJSON(v interface{}) string {
	rv := reflect.ValueOf(v)
	if rv.Kind() == reflect.Slice && rv.IsNil() {
		return "[]"
	}
	b, err := json.Marshal(v)
	if err != nil {
		return "null"
	}
	return string(b)
}

func guard(i int) {
	if r := recover(); r != nil {
		fmt.Println(tk, "E", i, fmt.Sprint(r))
	}
}
__METHODS__
func main() {
__CALLS__
}
'''

    def starter(self, args, ret, name):
        T, D = TYPES["go"], DEFAULTS["go"]
        ps = ", ".join(f"{a} {T[t]}" for a, t in args)
        return f"package main\n\nfunc {name}({ps}) {T[ret]} {{\n\t// your code here\n\treturn {D[ret]}\n}}\n"

    def program_template(self):
        return ('package main\n\nimport "fmt"\n\nfunc main() {\n\tnums := []int{5, 3, 8}\n\ttotal := 0\n\tfor _, n := range nums {\n\t\ttotal += n\n\t}\n\tfmt.Println(total)\n}\n')

    def program_files(self, code): return {"main.go": code}

    def test_files(self, code, args, ret, name, tests, tk):
        methods, calls = [], []
        for i, t in enumerate(tests):
            a = ", ".join(lit("go", ty, v) for (_, ty), v in zip(args, t["input"]))
            methods.append(f"func t{i}() {{\n\tdefer guard({i})\n\tr := {name}({a})\n\tfmt.Println(tk, \"T\", {i}, toJSON(r))\n}}\n")
            calls.append(f"\tt{i}()")
        drv = self.DRIVER.replace("__TK__", tk).replace("__METHODS__", "\n".join(methods)).replace("__CALLS__", "\n".join(calls))
        return {"solution.go": code, "main.go": drv}

    def build(self, tc, wd, files):
        return [[tc["go"], "build", "-o", "prog.exe" if IS_WIN else "prog", *sorted(f for f in files if f.endswith(".go"))]]

    def run_cmd(self, tc, wd, files): return [str(Path(wd) / ("prog.exe" if IS_WIN else "prog"))]


class CSharp(Lang):
    id, label, ext = "csharp", "C#", "cs"
    CSPROJ = ('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>__TFM__</TargetFramework>'
              '<Nullable>disable</Nullable><ImplicitUsings>disable</ImplicitUsings><AssemblyName>app</AssemblyName>'
              '<InvariantGlobalization>true</InvariantGlobalization></PropertyGroup></Project>')
    DRIVER = r'''
using System;
using System.Text.Json;

public static class Program
{
    const string TK = "__TK__";
    static string J(object o) { return JsonSerializer.Serialize(o, o == null ? typeof(object) : o.GetType()); }
__METHODS__
    public static void Main()
    {
        var s = new Solution();
__CALLS__
    }
}
'''

    def fn_name(self, py): return pascal(py)

    def starter(self, args, ret, name):
        T = TYPES["csharp"]
        ps = ", ".join(f"{T[t]} {a}" for a, t in args)
        return ("using System;\nusing System.Collections.Generic;\nusing System.Linq;\n\npublic class Solution\n{\n"
                f"    public {T[ret]} {name}({ps})\n    {{\n        // your code here\n        return default;\n    }}\n}}\n")

    def program_template(self):
        return ("using System;\n\npublic class Program\n{\n    public static void Main()\n    {\n        int[] nums = { 5, 3, 8 };\n        int total = 0;\n"
                "        foreach (int n in nums)\n        {\n            total += n;\n        }\n        Console.WriteLine(total);\n    }\n}\n")

    def _tfm(self):
        tc = toolchains().get("csharp") or {}
        return tc.get("tfm", "net8.0")

    def program_files(self, code):
        return {"Program.cs": code, "app.csproj": self.CSPROJ.replace("__TFM__", self._tfm())}

    def test_files(self, code, args, ret, name, tests, tk):
        methods, calls = [], []
        for i, t in enumerate(tests):
            a = ", ".join(lit("csharp", ty, v) for (_, ty), v in zip(args, t["input"]))
            methods.append(f"    static void T{i}(Solution s)\n    {{\n        var r = s.{name}({a});\n        Console.WriteLine(TK + \" T {i} \" + J(r));\n    }}\n")
            calls.append(f"        try {{ T{i}(s); }} catch (Exception e) {{ Console.WriteLine(TK + \" E {i} \" + e.GetType().Name + \": \" + e.Message.Replace(\"\\n\", \" \")); }}")
        drv = self.DRIVER.replace("__TK__", tk).replace("__METHODS__", "\n".join(methods)).replace("__CALLS__", "\n".join(calls))
        return {"Solution.cs": code, "Program.cs": drv, "app.csproj": self.CSPROJ.replace("__TFM__", self._tfm())}

    def build(self, tc, wd, files):
        return [[tc["dotnet"], "build", "-c", "Release", "-o", "out", "--nologo", "-v", "q", "-clp:NoSummary"]]

    def run_cmd(self, tc, wd, files): return [tc["dotnet"], str(Path(wd) / "out" / "app.dll")]

    def env(self):
        return {"DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "DOTNET_CLI_HOME": tempfile.gettempdir()}


LANGS = {l.id: l for l in (Python(), JavaScript(), TypeScript(), Java(), Cpp(), Go(), CSharp())}
ORDER = list(LANGS)

# ------------------------------------------------------------------ toolchain detection
_cache = {"at": 0, "tc": {}}


def _first(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def _out(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception:
        return ""


def _probe(cmd):
    """Run a version command. Returns (started_ok, output). A binary that exists but cannot start
    (e.g. blocked by Windows App Control / Smart App Control, or a broken install) is NOT usable."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception:
        return False, ""


def _smart_app_control_on():
    """True when Windows Smart App Control is enforcing (it blocks every unsigned program, including ones you compile)."""
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            return winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")[0] == 1
    except Exception:
        return False


def _is_signed(path):
    """Reads a file's Authenticode signature WITHOUT running it (so no security prompt is triggered)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            f"(Get-AuthenticodeSignature -LiteralPath '{path}').Status"], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() == "Valid"
    except Exception:
        return True  # unknown: fall back to actually trying it


SAC_MSG = "Windows Smart App Control is on and blocks unsigned programs, which includes anything this toolchain builds or runs."


def _can_run_compiled(cxx):
    """Compile and run a trivial program. False only when the OS refuses to start the built executable."""
    wd = tempfile.mkdtemp(prefix="lb_probe_")
    try:
        (Path(wd) / "p.cpp").write_text("int main() { return 0; }\n")
        exe = "p.exe" if IS_WIN else "p"
        r = subprocess.run([cxx, "-o", exe, "p.cpp"], cwd=wd, capture_output=True, timeout=90)
        if r.returncode != 0:
            return True  # a compile problem: let real runs show the compiler's message
        subprocess.run([str(Path(wd) / exe)], timeout=15)
        return True
    except OSError:
        return False
    except Exception:
        return True
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def _detect():
    tc, problems = {"python": {"python": sys.executable}}, {}

    sac = _smart_app_control_on()

    def usable(lang, path, args):
        if sac and not _is_signed(path):  # don't even launch it: launching is what raises the Windows security warning
            problems[lang] = f"{Path(path).name} is unsigned. {SAC_MSG}"
            return False, ""
        ok, out = _probe([path, *args])
        if not ok:
            problems[lang] = f"{Path(path).name} was found but cannot run here (blocked by a system security policy, or a broken install)."
        return ok, out

    node = _first("node")
    if node:
        ok, out = usable("javascript", node, ["--version"])
        if ok:
            tc["javascript"] = {"node": node}
            m = re.search(r"v(\d+)\.(\d+)", out)
            tsc = _first("tsc")
            if m and (int(m[1]), int(m[2])) >= (22, 6):
                tc["typescript"] = {"node": node, "mode": "strip"}
            elif tsc:
                tc["typescript"] = {"node": node, "tsc": tsc, "mode": "tsc"}
    javac, java = _first("javac"), _first("java")
    if javac and java and usable("java", javac, ["-version"])[0] and usable("java", java, ["-version"])[0]:
        tc["java"] = {"javac": javac, "java": java}
    cxx = _first("g++", "clang++", "c++")
    if cxx and sac:
        # programs g++/clang++ build are never signed, so they would all be blocked: skip the build-and-run probe entirely
        problems["cpp"] = f"The compiler works, but programs it builds are unsigned. {SAC_MSG}"
    elif cxx and usable("cpp", cxx, ["--version"])[0]:
        if _can_run_compiled(cxx):
            tc["cpp"] = {"cxx": cxx}
        else:
            problems["cpp"] = "The compiler works, but Windows blocks running programs you build (an App Control policy)."
    go = _first("go")
    if go and usable("go", go, ["version"])[0]:
        tc["go"] = {"go": go}
    dn = _first("dotnet")
    if dn and sac:
        # dotnet itself is signed, but the app.dll it builds is not, and Smart App Control blocks loading it
        problems["csharp"] = f"The .NET SDK works, but the program it builds (app.dll) is unsigned. {SAC_MSG}"
    elif dn:
        ok, out = usable("csharp", dn, ["--version"])
        m = re.search(r"^(\d+)\.", out.strip())
        if ok and m:
            tc["csharp"] = {"dotnet": dn, "tfm": f"net{m[1]}.0"}
    tc["_problems"] = problems
    return tc


def toolchains(refresh=False):
    if refresh or time.time() - _cache["at"] > 300 or not _cache["tc"]:
        _cache["tc"], _cache["at"] = _detect(), time.time()
    return {k: v for k, v in _cache["tc"].items() if k != "_problems"}


def problem_for(lang):
    return (_cache["tc"].get("_problems") or {}).get(lang, "")


HINTS = {
    "javascript": ("winget install OpenJS.NodeJS.LTS", "brew install node", "sudo apt install nodejs"),
    "typescript": ("winget install OpenJS.NodeJS.LTS  (Node 22.6+ runs TypeScript directly)", "brew install node  (Node 22.6+)", "install Node 22.6+ (nodejs.org), or: npm i -g typescript"),
    "java": ("winget install EclipseAdoptium.Temurin.21.JDK", "brew install openjdk", "sudo apt install default-jdk"),
    "cpp": ("winget install BrechtSanders.WinLibs.POSIX.UCRT", "xcode-select --install", "sudo apt install g++"),
    "go": ("winget install GoLang.Go", "brew install go", "sudo apt install golang-go"),
    "csharp": ("winget install Microsoft.DotNet.SDK.8", "brew install --cask dotnet-sdk", "sudo apt install dotnet-sdk-8.0"),
}


def install_hint(lang):
    h = HINTS.get(lang)
    if not h:
        return ""
    cmd = h[0] if IS_WIN else h[1] if sys.platform == "darwin" else h[2]
    prob = problem_for(lang)
    if prob and "Smart App Control" in prob:
        return prob + " Use Java, JavaScript or TypeScript here (their runtimes are signed), or run LogicBuilder inside WSL/Docker or on macOS/Linux."
    return (prob + " " if prob else "") + f"Install: {cmd}   (then restart LogicBuilder)"


def catalog(refresh=False):
    tc = toolchains(refresh)
    return [{"id": l.id, "label": l.label, "ext": l.ext, "visualize": l.visualize, "available": l.id in tc,
             "hint": "" if l.id in tc else install_hint(l.id), "template": l.program_template()} for l in LANGS.values()]


def starters(sig, py_entry, py_starter):
    args, ret = sig
    out = {}
    for l in LANGS.values():
        out[l.id] = py_starter if l.id == "python" else l.starter(args, ret, l.fn_name(py_entry))
    return out


# ------------------------------------------------------------------ execution
def _run(cmd, cwd, timeout, tag, env=None):
    """Run a process with a wall-clock limit and an output-size cap. Returns (rc, out, err, status)."""
    wd = Path(cwd)
    op, ep = wd / f"_{tag}.out", wd / f"_{tag}.err"
    full_env = {**os.environ, **(env or {})}
    status = "ok"
    with open(op, "wb") as fo, open(ep, "wb") as fe:
        try:
            p = subprocess.Popen(cmd, cwd=cwd, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL, env=full_env)
        except OSError as e:
            return -1, "", f"Could not start {Path(cmd[0]).name}: {e}", "error"
        deadline = time.time() + timeout
        while True:
            rc = p.poll()
            if rc is not None:
                break
            if time.time() > deadline:
                p.kill(); p.wait(); rc, status = None, "timeout"
                break
            try:
                if op.stat().st_size > MAX_FILE:
                    p.kill(); p.wait(); rc, status = None, "flood"
                    break
            except OSError:
                pass
            time.sleep(0.02)
    read = lambda f: f.read_bytes()[:MAX_OUT].decode("utf-8", "replace")  # noqa: E731
    return rc, read(op), read(ep), status


def _clean(msg, wd):
    msg = msg.replace(str(wd) + os.sep, "").replace(str(wd), "").replace("\r", "")
    return msg.strip()[:1500]


def _node_syntax_error(L, err):
    """Node reports TypeScript/JS syntax errors at run time; treat them as compile errors."""
    if L.id in ("javascript", "typescript") and ("SyntaxError" in err or "ERR_INVALID_TYPESCRIPT_SYNTAX" in err):
        keep = []
        for ln in err.replace("\r", "").splitlines():
            if ln.startswith("    at ") or ln.startswith("Node.js v"):
                break
            keep.append(ln)
        return "\n".join(keep).strip()[:1500] or "Syntax error"
    return None


def _err_line(msg):
    m = re.search(r"\.(?:java|cpp|h|go|cs|ts|js)[:(](\d+)", msg)
    return int(m[1]) if m else None


def _prepare(lang, files, wd, tc):
    for name, content in files.items():
        with open(Path(wd) / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    L = LANGS[lang]
    for k, cmd in enumerate(L.build(tc, wd, files)):
        rc, out, err, status = _run(cmd, wd, COMPILE_TIMEOUT, f"build{k}", L.env())
        if status == "timeout":
            return {"type": "CompileError", "message": "Compilation took too long.", "line": None}
        if rc != 0:
            msg = _clean(err + "\n" + out, wd)
            return {"type": "CompileError", "message": msg or "Compilation failed", "line": _err_line(msg)}
    return None


def _nolang(lang):
    L = LANGS[lang]
    return {"verdict": "NOLANG", "results": [], "stdout": "",
            "error": {"type": "NotInstalled", "message": f"{L.label} isn't installed on this computer. {install_hint(lang)}", "line": None}}


def run_program(lang, code, timeout=6):
    """Playground: run a complete program."""
    if lang == "python":
        return sandbox.execute("run", code, timeout=timeout)
    tc = toolchains().get(lang)
    if not tc:
        return _nolang(lang)
    L = LANGS[lang]
    wd = tempfile.mkdtemp(prefix="lb_")
    try:
        files = L.program_files(code)
        ce = _prepare(lang, files, wd, tc)
        if ce:
            return {"verdict": "CE", "error": ce, "stdout": ""}
        rc, out, err, status = _run(L.run_cmd(tc, wd, files), wd, timeout, "run", L.env())
        if status == "timeout":
            return {"verdict": "TLE", "stdout": out[:4000], "error": {"type": "TimeLimit", "message": f"Your code ran longer than {timeout}s (infinite loop?)", "line": None}}
        if status == "flood":
            return {"verdict": "RE", "stdout": out[:4000], "error": {"type": "OutputLimit", "message": "Too much output", "line": None}}
        if rc != 0:
            se = _node_syntax_error(L, err)
            if se:
                return {"verdict": "CE", "stdout": "", "error": {"type": "CompileError", "message": se, "line": _err_line(se)}}
            return {"verdict": "RE", "stdout": out[:4000], "error": {"type": "RuntimeError", "message": _clean(err, wd)[-800:] or f"exit code {rc}", "line": None}}
        return {"verdict": "OK", "stdout": out[:4000], "error": None}
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def judge(lang, code, sig, py_entry, tests, timeout=6):
    """Run learner's function against tests. Same result shape as sandbox.execute('test')."""
    if lang == "python":
        return sandbox.execute("test", code, entry=py_entry, tests=tests, timeout=timeout)
    tc = toolchains().get(lang)
    if not tc:
        return _nolang(lang)
    L = LANGS[lang]
    args, ret = sig
    tk = "@@" + secrets.token_hex(6)
    wd = tempfile.mkdtemp(prefix="lb_")
    try:
        files = L.test_files(code, args, ret, L.fn_name(py_entry), tests, tk)
        ce = _prepare(lang, files, wd, tc)
        if ce:
            return {"verdict": "CE", "error": ce, "results": [], "stdout": ""}
        rc, out, err, status = _run(L.run_cmd(tc, wd, files), wd, timeout, "run", L.env())
        se = _node_syntax_error(L, err) if rc not in (0, None) else None
        if se:
            return {"verdict": "CE", "error": {"type": "CompileError", "message": se, "line": _err_line(se)}, "results": [], "stdout": ""}
        marks, user = {}, []
        for line in out.splitlines():
            i = line.find(tk + " ")
            if i < 0:
                user.append(line)
                continue
            if line[:i].strip():
                user.append(line[:i])
            parts = line[i + len(tk) + 1:].split(" ", 2)
            try:
                marks[int(parts[1])] = (parts[0], parts[2] if len(parts) > 2 else "")
            except (ValueError, IndexError):
                continue
        results = []
        for k, t in enumerate(tests):
            if k not in marks:
                results.append({"pass": False, "error": "No result (the program crashed or ran out of time)"})
                continue
            kind, payload = marks[k]
            if kind == "E":
                results.append({"pass": False, "error": payload[:300]})
                continue
            try:
                actual = json.loads(payload)
            except ValueError:
                results.append({"pass": False, "error": "Could not read the returned value"})
                continue
            results.append({"pass": actual == t["expected"], "actual": actual})
        stdout = "\n".join(user)[:4000]
        if status == "timeout":
            verdict, error = "TLE", {"type": "TimeLimit", "message": f"Your code ran longer than {timeout}s (infinite loop or too slow)", "line": None}
        elif status == "flood":
            verdict, error = "RE", {"type": "OutputLimit", "message": "Too much output", "line": None}
        elif len(marks) < len(tests) and rc not in (0, None):
            verdict, error = "RE", {"type": "RuntimeError", "message": _clean(err, wd)[-600:] or f"program crashed (exit code {rc})", "line": None}
        else:
            error = None
            ok = all(r["pass"] for r in results)
            verdict = "AC" if ok else ("RE" if any("error" in r for r in results) else "WA")
        return {"verdict": verdict, "error": error, "results": results, "stdout": stdout}
    finally:
        shutil.rmtree(wd, ignore_errors=True)
