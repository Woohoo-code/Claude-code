"""Live JLCPCB stock / library class for every assembly BOM line."""
import csv, json, subprocess, sys, time
def q(code):
    for a in range(4):
        out = subprocess.run(["curl", "-sS", "-m", "30", "-X", "POST",
            "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList",
            "-H", "Content-Type: application/json", "-d", json.dumps({"keyword": code, "currentPage": 1, "pageSize": 10})],
            capture_output=True, text=True).stdout
        try:
            return next(c for c in json.loads(out)["data"]["componentPageInfo"]["list"] if c["componentCode"] == code)
        except Exception:
            time.sleep(3 * (a + 1))
boards = int(sys.argv[2]) if len(sys.argv) > 2 else 5
worst = []; fee = 0; ok = True
for r in csv.DictReader(open(sys.argv[1])):
    n = len(r["Designator"].split(",")) * boards; c = q(r["LCSC Part #"])
    if c is None: print(f"{r['LCSC Part #']}: NOT FOUND"); ok = False; continue
    free = c["componentLibraryType"] == "base" or c["preferredComponentFlag"]
    fee += not free
    cover = c["stockCount"] / n
    worst.append((cover, r["LCSC Part #"], r["Comment"], c["stockCount"], n))
    if c["stockCount"] < n: ok = False
    time.sleep(0.2)
worst.sort()
print(f"{len(worst)} lines, {fee} extended part types; lowest stock cover for {boards} boards:")
for cover, code, com, st, n in worst[:5]:
    print(f"   {code:9} {com:14} stock {st:>7} for {n:3} needed ({cover:,.0f}x)")
print("STOCK: " + ("ALL IN STOCK" if ok else "SHORTAGE"))
