"""Multi-language tests. Run: python tests/lang_test.py
Codegen is always checked. Execution is checked for each language whose toolchain is installed;
others are reported as SKIP (never silently passed)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from app import langs  # noqa: E402
from content.problems import PROBLEMS  # noqa: E402
from content.signatures import SIGS  # noqa: E402

P = {p["slug"]: p for p in PROBLEMS}
fails = 0


def check(name, ok, info=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    fails += 0 if ok else 1


# ---------------------------------------------------------------- codegen (no toolchain needed)
check("every problem has a signature", set(SIGS) == set(P))
for slug, p in P.items():
    args, ret = SIGS[slug]
    check(f"{slug}: signature arity matches tests", all(len(t["input"]) == len(args) for t in p["tests"]))
    st = langs.starters(SIGS[slug], p["entry"], p["starter"])
    check(f"{slug}: starters for all languages", set(st) == set(langs.LANGS) and all(st.values()))
    for lid, L in langs.LANGS.items():
        if lid == "python":
            continue
        name = L.fn_name(p["entry"])
        check(f"{slug}/{lid}: starter declares {name}", name in st[lid])
        files = L.test_files(st[lid], args, ret, name, p["tests"], "@@TKTEST")
        blob = "\n".join(files.values())
        check(f"{slug}/{lid}: driver has token and all {len(p['tests'])} tests", "@@TKTEST" in blob and (f"t{len(p['tests']) - 1}" in blob.lower() or "__tests" in blob))

check("camel/pascal naming", langs.camel("is_valid") == "isValid" and langs.pascal("two_sum") == "TwoSum")
cat = {c["id"]: c for c in langs.catalog(refresh=True)}
check("catalog lists 7 languages", len(cat) == 7 and cat["python"]["available"])
check("missing language has install hint", all(c["available"] or "Install:" in c["hint"] or "Smart App Control" in c["hint"] for c in cat.values()))
nl = langs.judge("java", "x", SIGS["even-or-odd"], "even_or_odd", P["even-or-odd"]["tests"]) if not cat["java"]["available"] else None
check("missing toolchain reports NOLANG (not a crash)", nl is None or nl["verdict"] == "NOLANG")

# ---------------------------------------------------------------- execution (per installed language)
REFS = {
    "javascript": {
        "fizzbuzz": 'function fizzbuzz(n) { const out = []; for (let i = 1; i <= n; i++) { if (i % 15 === 0) out.push("FizzBuzz"); else if (i % 3 === 0) out.push("Fizz"); else if (i % 5 === 0) out.push("Buzz"); else out.push(String(i)); } return out; }',
        "two-sum": 'function twoSum(nums, target) { const seen = new Map(); for (let i = 0; i < nums.length; i++) { const need = target - nums[i]; if (seen.has(need)) return [seen.get(need), i]; seen.set(nums[i], i); } return []; }',
        "palindrome": 'function isPalindrome(s) { const t = s.toLowerCase().replace(/[^a-z0-9]/g, ""); let l = 0, r = t.length - 1; while (l < r) { if (t[l] !== t[r]) return false; l++; r--; } return true; }',
        "factorial": 'function factorial(n) { let r = 1; for (let i = 2; i <= n; i++) r *= i; return r; }',
    },
    "typescript": {
        "fizzbuzz": 'function fizzbuzz(n: number): string[] { const out: string[] = []; for (let i = 1; i <= n; i++) { if (i % 15 === 0) out.push("FizzBuzz"); else if (i % 3 === 0) out.push("Fizz"); else if (i % 5 === 0) out.push("Buzz"); else out.push(String(i)); } return out; }',
        "two-sum": 'function twoSum(nums: number[], target: number): number[] { const seen = new Map<number, number>(); for (let i = 0; i < nums.length; i++) { const need = target - nums[i]; if (seen.has(need)) return [seen.get(need) as number, i]; seen.set(nums[i], i); } return []; }',
        "palindrome": 'function isPalindrome(s: string): boolean { const t = s.toLowerCase().replace(/[^a-z0-9]/g, ""); let l = 0, r = t.length - 1; while (l < r) { if (t[l] !== t[r]) return false; l++; r--; } return true; }',
        "factorial": 'function factorial(n: number): number { let r = 1; for (let i = 2; i <= n; i++) r *= i; return r; }',
    },
    "java": {
        "fizzbuzz": 'class Solution { public String[] fizzbuzz(int n) { String[] out = new String[n]; for (int i = 1; i <= n; i++) { if (i % 15 == 0) out[i-1] = "FizzBuzz"; else if (i % 3 == 0) out[i-1] = "Fizz"; else if (i % 5 == 0) out[i-1] = "Buzz"; else out[i-1] = String.valueOf(i); } return out; } }',
        "two-sum": 'import java.util.*;\nclass Solution { public int[] twoSum(int[] nums, int target) { Map<Integer,Integer> seen = new HashMap<>(); for (int i = 0; i < nums.length; i++) { int need = target - nums[i]; if (seen.containsKey(need)) return new int[]{seen.get(need), i}; seen.put(nums[i], i); } return new int[0]; } }',
        "palindrome": 'class Solution { public boolean isPalindrome(String s) { StringBuilder t = new StringBuilder(); for (char c : s.toCharArray()) if (Character.isLetterOrDigit(c)) t.append(Character.toLowerCase(c)); int l = 0, r = t.length() - 1; while (l < r) { if (t.charAt(l) != t.charAt(r)) return false; l++; r--; } return true; } }',
        "factorial": 'class Solution { public long factorial(int n) { long r = 1; for (int i = 2; i <= n; i++) r *= i; return r; } }',
    },
    "cpp": {
        "fizzbuzz": 'class Solution { public: vector<string> fizzbuzz(int n) { vector<string> out; for (int i = 1; i <= n; i++) { if (i % 15 == 0) out.push_back("FizzBuzz"); else if (i % 3 == 0) out.push_back("Fizz"); else if (i % 5 == 0) out.push_back("Buzz"); else out.push_back(to_string(i)); } return out; } };',
        "two-sum": 'class Solution { public: vector<int> twoSum(vector<int>& nums, int target) { unordered_map<int,int> seen; for (int i = 0; i < (int)nums.size(); i++) { int need = target - nums[i]; auto it = seen.find(need); if (it != seen.end()) return {it->second, i}; seen[nums[i]] = i; } return {}; } };',
        "palindrome": 'class Solution { public: bool isPalindrome(string s) { string t; for (char c : s) if (isalnum((unsigned char)c)) t += (char)tolower((unsigned char)c); int l = 0, r = (int)t.size() - 1; while (l < r) { if (t[l] != t[r]) return false; l++; r--; } return true; } };',
        "factorial": 'class Solution { public: long long factorial(int n) { long long r = 1; for (int i = 2; i <= n; i++) r *= i; return r; } };',
    },
    "go": {
        "fizzbuzz": 'package main\n\nimport "strconv"\n\nfunc fizzbuzz(n int) []string {\n\tout := []string{}\n\tfor i := 1; i <= n; i++ {\n\t\tswitch {\n\t\tcase i%15 == 0:\n\t\t\tout = append(out, "FizzBuzz")\n\t\tcase i%3 == 0:\n\t\t\tout = append(out, "Fizz")\n\t\tcase i%5 == 0:\n\t\t\tout = append(out, "Buzz")\n\t\tdefault:\n\t\t\tout = append(out, strconv.Itoa(i))\n\t\t}\n\t}\n\treturn out\n}\n',
        "two-sum": 'package main\n\nfunc twoSum(nums []int, target int) []int {\n\tseen := map[int]int{}\n\tfor i, x := range nums {\n\t\tif j, ok := seen[target-x]; ok {\n\t\t\treturn []int{j, i}\n\t\t}\n\t\tseen[x] = i\n\t}\n\treturn nil\n}\n',
        "palindrome": 'package main\n\nimport (\n\t"strings"\n\t"unicode"\n)\n\nfunc isPalindrome(s string) bool {\n\tvar t []rune\n\tfor _, c := range strings.ToLower(s) {\n\t\tif unicode.IsLetter(c) || unicode.IsDigit(c) {\n\t\t\tt = append(t, c)\n\t\t}\n\t}\n\tfor l, r := 0, len(t)-1; l < r; l, r = l+1, r-1 {\n\t\tif t[l] != t[r] {\n\t\t\treturn false\n\t\t}\n\t}\n\treturn true\n}\n',
        "factorial": 'package main\n\nfunc factorial(n int) int {\n\tr := 1\n\tfor i := 2; i <= n; i++ {\n\t\tr *= i\n\t}\n\treturn r\n}\n',
    },
    "csharp": {
        "fizzbuzz": 'using System;\nusing System.Collections.Generic;\npublic class Solution { public string[] Fizzbuzz(int n) { var o = new List<string>(); for (int i = 1; i <= n; i++) { if (i % 15 == 0) o.Add("FizzBuzz"); else if (i % 3 == 0) o.Add("Fizz"); else if (i % 5 == 0) o.Add("Buzz"); else o.Add(i.ToString()); } return o.ToArray(); } }',
        "two-sum": 'using System;\nusing System.Collections.Generic;\npublic class Solution { public int[] TwoSum(int[] nums, int target) { var seen = new Dictionary<int,int>(); for (int i = 0; i < nums.Length; i++) { int need = target - nums[i]; if (seen.ContainsKey(need)) return new int[]{seen[need], i}; seen[nums[i]] = i; } return new int[0]; } }',
        "palindrome": 'using System;\nusing System.Text;\npublic class Solution { public bool IsPalindrome(string s) { var t = new StringBuilder(); foreach (char c in s) if (char.IsLetterOrDigit(c)) t.Append(char.ToLower(c)); int l = 0, r = t.Length - 1; while (l < r) { if (t[l] != t[r]) return false; l++; r--; } return true; } }',
        "factorial": 'using System;\npublic class Solution { public long Factorial(int n) { long r = 1; for (int i = 2; i <= n; i++) r *= i; return r; } }',
    },
}
# factorial variants used for negative tests
CRASH = {
    "javascript": 'function factorial(n) { throw new Error("boom"); }',
    "typescript": 'function factorial(n: number): number { throw new Error("boom"); }',
    "java": 'class Solution { public long factorial(int n) { throw new RuntimeException("boom"); } }',
    "cpp": 'class Solution { public: long long factorial(int n) { throw std::runtime_error("boom"); } };',
    "go": 'package main\n\nfunc factorial(n int) int {\n\tpanic("boom")\n}\n',
    "csharp": 'using System;\npublic class Solution { public long Factorial(int n) { throw new Exception("boom"); } }',
}
LOOP = {
    "javascript": 'function factorial(n) { while (true) {} }',
    "typescript": 'function factorial(n: number): number { while (true) {} }',
    "java": 'class Solution { public long factorial(int n) { while (true) {} } }',
    "cpp": 'class Solution { public: long long factorial(int n) { while (true) {} return 0; } };',
    "go": 'package main\n\nfunc factorial(n int) int {\n\tfor {\n\t}\n}\n',
    "csharp": 'public class Solution { public long Factorial(int n) { while (true) {} } }',
}
BROKEN = {
    "javascript": 'function factorial(n) { return ; ) }',
    "typescript": 'function factorial(n: number): number { return ; ) }',
    "java": 'class Solution { public long factorial(int n) { return ; } ',
    "cpp": 'class Solution { public: long long factorial(int n) { return ; } };',
    "go": 'package main\n\nfunc factorial(n int) int {\n\treturn ;;; )\n}\n',
    "csharp": 'public class Solution { public long Factorial(int n) { return ; } ',
}
HELLO = {
    "javascript": 'console.log("hi " + (6 * 7));', "typescript": 'const x: number = 6 * 7;\nconsole.log("hi " + x);',
    "java": 'public class Main { public static void main(String[] a) { System.out.println("hi " + (6 * 7)); } }',
    "cpp": '#include <iostream>\nint main() { std::cout << "hi " << 6 * 7 << std::endl; }',
    "go": 'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println("hi", 6*7) }\n',
    "csharp": 'using System;\npublic class Program { public static void Main() { Console.WriteLine("hi " + (6 * 7)); } }',
}


def judge(lang, slug, code, timeout=6):
    p = P[slug]
    return langs.judge(lang, code, SIGS[slug], p["entry"], p["tests"], timeout=timeout)


tcs = langs.toolchains(refresh=True)
for lid in langs.LANGS:
    if lid == "python":
        continue
    if lid not in tcs:
        print(f"SKIP {lid}: toolchain not installed ({langs.install_hint(lid)})")
        continue
    for slug, code in REFS[lid].items():
        r = judge(lid, slug, code)
        check(f"{lid}: reference solves {slug}", r["verdict"] == "AC", r)
    st = langs.starters(SIGS["factorial"], "factorial", "")[lid]
    r = judge(lid, "factorial", st)
    check(f"{lid}: untouched starter compiles and fails (WA)", r["verdict"] == "WA", r)
    r = judge(lid, "factorial", BROKEN[lid])
    check(f"{lid}: syntax error -> CE with message", r["verdict"] == "CE" and r["error"]["message"], r)
    r = judge(lid, "factorial", CRASH[lid])
    check(f"{lid}: exception -> RE and mentions boom", r["verdict"] == "RE" and "boom" in str(r), r)
    r = judge(lid, "factorial", LOOP[lid], timeout=3)
    check(f"{lid}: infinite loop -> TLE", r["verdict"] == "TLE", r)
    r = langs.run_program(lid, HELLO[lid])
    check(f"{lid}: playground run prints output", r["verdict"] == "OK" and "hi 42" in r["stdout"], r)
    r = langs.run_program(lid, langs.LANGS[lid].program_template())
    check(f"{lid}: default playground template prints 16", r["verdict"] == "OK" and r["stdout"].strip() == "16", r)

# ---- every problem's generated starter + driver must at least COMPILE/parse (no CE) in each usable language
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

for lid in langs.LANGS:
    if lid not in tcs or lid == "python":
        continue
    bad = []
    for slug, p in P.items():
        st = langs.starters(SIGS[slug], p["entry"], p["starter"])[lid]
        r = langs.judge(lid, st, SIGS[slug], p["entry"], p["tests"][:2]) if False else langs.judge(lid, st, SIGS[slug], p["entry"], p["tests"])
        if r["verdict"] in ("CE",):
            bad.append((slug, r["error"]["message"][:200]))
    check(f"{lid}: generated starter+driver compiles for all {len(P)} problems", not bad, bad[:2])

# C++ where the compiler exists but this OS refuses to run built programs: verify syntax only
if "cpp" not in tcs and shutil.which("g++"):
    bad = []
    for slug, p in P.items():
        L = langs.LANGS["cpp"]
        args, ret = SIGS[slug]
        st = langs.starters(SIGS[slug], p["entry"], p["starter"])["cpp"]
        files = L.test_files(st, args, ret, L.fn_name(p["entry"]), p["tests"], "@@TK")
        wd = tempfile.mkdtemp(prefix="lb_syn_")
        for n, c in files.items():
            Path(wd, n).write_text(c)
        r = subprocess.run([shutil.which("g++"), "-std=c++17", "-fsyntax-only", "main.cpp"], cwd=wd, capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((slug, r.stderr[:300]))
        shutil.rmtree(wd, ignore_errors=True)
    check(f"cpp (syntax-only, execution blocked by OS policy): all {len(P)} drivers compile", not bad, bad[:1])

# Python through the same entry points
r = judge("python", "factorial", P["factorial"]["reference"])
check("python via langs.judge", r["verdict"] == "AC")
r = langs.run_program("python", 'print("hi", 6 * 7)')
check("python via langs.run_program", r["verdict"] == "OK" and "hi 42" in r["stdout"])

print("\nALL OK" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
