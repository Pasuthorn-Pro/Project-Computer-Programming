import struct
import datetime as dt
import os

# ===============================
# Utils
# ===============================
def pad_str(s: str, length: int) -> bytes:
    b = s.encode("utf-8")[:length]
    return b + b" " * (length - len(b))

def read_str(b: bytes) -> str:
    return b.decode("utf-8").rstrip()

def today_str() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

DEFAULT_TEAM_NAMES = {
    1:"Arsenal",
    2:"Chelsea",
    3:"Liverpool",
    4:"Manchester City",
    5:"Manchester United",
    6:"Tottenham Hotspur",
    99:"Other Team",
}
DEFAULT_TEAM_CODES = {
    1:"ARS", 2:"CHE", 3:"LIV", 4:"MCI", 5:"MUN", 6:"TOT", 99:"OTH",
}

def yyyymmdd_to_str(d8: int) -> str:
    y = d8 // 10000
    m = (d8 % 10000) // 100
    d = d8 % 100
    if not (1 <= m <= 12):
        return str(d8)
    return f"{y}-{MONTHS[m-1]}-{d:02d}"

VALID_POS   = {"FW","MF","DF","GK","CF","AMF","DMF","CMF","RWF","LWF","RMF","LMF","CB","RB","LB"}
VALID_TEAMS = {1,2,3,4,5,6,99}

def fmt_money(x: float) -> str:
    return f"{x:.2f}"

# forward decls use these readers
def get_team_map():
    teams = {}
    try:
        for t in read_teams():
            teams[t["id"]] = t
    except Exception:
        pass
    return teams

def team_name_by_id(team_id: int, teams_map: dict) -> str:
    # ใช้ชื่อจากไฟล์ teams.dat ถ้ามี ไม่งั้น fallback เป็นชื่อทีม Big6
    return teams_map.get(team_id, {}).get("name") or DEFAULT_TEAM_NAMES.get(team_id, str(team_id))

def team_code_by_id(team_id: int, teams_map: dict) -> str:
    return teams_map.get(team_id, {}).get("code") or DEFAULT_TEAM_CODES.get(team_id, str(team_id))

def ensure_unique_player_id(pid: int):
    if any(p["id"] == pid for p in read_players()):
        raise ValueError("มี Player ID นี้แล้ว")

def ensure_unique_transfer_id(tid: int):
    if any(t["id"] == tid for t in read_transfers()):
        raise ValueError("มี Transfer ID นี้แล้ว")

def require_team_id(x: int) -> int:
    if x not in VALID_TEAMS:
        raise ValueError("Team ID ต้องเป็น 1-6 หรือ 99 (OTH)")
    return x

def require_position(p: str) -> str:
    u = p.upper()
    if u not in VALID_POS:
        raise ValueError(f"Position ไม่ถูกต้อง (ใช้ {', '.join(sorted(VALID_POS))})")
    return u

def find_player(pid: int):
    for p in read_players():
        if p["id"] == pid:
            return p
    return None

# ===============================
# TEAM
# ===============================
TEAM_STRUCT = struct.Struct("<H20s4sB")  # id:uint16, name:20s, code:4s, big6:bool

def add_team(team_id: int, name: str, code: str, big6: bool, path="teams.dat"):
    with open(path, "ab") as f:
        f.write(TEAM_STRUCT.pack(team_id, pad_str(name, 20), pad_str(code, 4), int(big6)))

def read_teams(path="teams.dat"):
    teams = []
    if not os.path.exists(path): return teams
    with open(path, "rb") as f:
        while True:
            b = f.read(TEAM_STRUCT.size)
            if not b or len(b) < TEAM_STRUCT.size: break
            team_id, name, code, big6 = TEAM_STRUCT.unpack(b)
            teams.append({"id": team_id, "name": read_str(name), "code": read_str(code), "big6": bool(big6)})
    return teams

# ===============================
# PLAYER
# ===============================
# NOTE: fixed format (no spaces): id:i, name:40s, pos:4s, age:i, price:f, team_id:H, active:B
PLAYER_STRUCT = struct.Struct("<i40s4sifHB")

def add_player(pid: int, name: str, pos: str, age: int, price: float, team_id: int, active=True, path="players.dat"):
    with open(path, "ab") as f:
        f.write(PLAYER_STRUCT.pack(
            pid, pad_str(name, 40), pad_str(pos, 4), int(age), float(price), int(team_id), int(active)
        ))

def read_players(path="players.dat"):
    rows = []
    if not os.path.exists(path): return rows
    with open(path, "rb") as f:
        while True:
            b = f.read(PLAYER_STRUCT.size)
            if not b or len(b) < PLAYER_STRUCT.size: break
            pid, name, pos, age, price, team_id, active = PLAYER_STRUCT.unpack(b)
            rows.append({
                "id": pid, "name": read_str(name), "pos": read_str(pos), "age": age,
                "price": float(price), "team_id": team_id, "active": bool(active)
            })
    return rows

def update_player(path="players.dat", pid=None, new_data=None):
    if not os.path.exists(path): return
    with open(path, "r+b") as f:
        idx = 0
        while True:
            b = f.read(PLAYER_STRUCT.size)
            if not b or len(b) < PLAYER_STRUCT.size: break
            cur = PLAYER_STRUCT.unpack(b)
            if cur[0] == pid:
                # cur = (id, name(bytes), pos(bytes), age, price, team_id, active)
                name = new_data.get("name", read_str(cur[1]))
                pos  = new_data.get("pos",  read_str(cur[2]))
                age  = new_data.get("age",  cur[3])
                price= new_data.get("price",cur[4])
                team = new_data.get("team_id", cur[5])
                active = int(new_data.get("active", cur[6]))
                f.seek(idx * PLAYER_STRUCT.size)
                f.write(PLAYER_STRUCT.pack(
                    cur[0], pad_str(name,40), pad_str(pos,4), int(age), float(price), int(team), active
                ))
                return
            idx += 1

# ===============================
# TRANSFER
# ===============================
# id:i, player_id:i, from:H, to:H, age:i, price:f, date:I, status:B, active:B
TRANSFER_STRUCT = struct.Struct("<iiHHifIBB")

def add_transfer(tid:int, pid:int, from_id:int, to_id:int, age:int, price:float,
                 date:int, status=True, active=True, path="transfers.dat", player_file="players.dat"):
    # เขียนดีล
    with open(path, "ab") as f:
        f.write(TRANSFER_STRUCT.pack(
            int(tid), int(pid), int(from_id), int(to_id), int(age), float(price), int(date), int(status), int(active)
        ))

    # อัปเดตทีมของผู้เล่น -> current_team_id = to_id
    if os.path.exists(player_file):
        with open(player_file, "r+b") as pf:
            idx = 0
            while True:
                b = pf.read(PLAYER_STRUCT.size)
                if not b or len(b) < PLAYER_STRUCT.size: break
                rec = PLAYER_STRUCT.unpack(b)
                if rec[0] == pid:
                    updated = (rec[0], rec[1], rec[2], rec[3], rec[4], int(to_id), rec[6])
                    pf.seek(idx * PLAYER_STRUCT.size)
                    pf.write(PLAYER_STRUCT.pack(*updated))
                    break
                idx += 1

def read_transfers(path="transfers.dat"):
    rows = []
    if not os.path.exists(path): return rows
    with open(path, "rb") as f:
        while True:
            b = f.read(TRANSFER_STRUCT.size)
            if not b or len(b) < TRANSFER_STRUCT.size: break
            tid, pid, from_id, to_id, age, price, date, status, active = TRANSFER_STRUCT.unpack(b)
            rows.append({
                "id": tid, "player_id": pid, "from": from_id, "to": to_id,
                "age": age, "price": float(price), "date": date,
                "status": bool(status), "active": bool(active)
            })
    return rows

# ===============================
# REPORT
# ===============================
def generate_report(team_file="teams.dat", player_file="players.dat",
                    transfer_file="transfers.dat", report_file="summary.txt"):
    teams_map   = get_team_map()
    players     = read_players()
    players_map = {p["id"]: p for p in players}
    transfers   = read_transfers()

    # ----- fallback team names -----
    DEFAULT_TEAM_NAMES = {
        1:"Arsenal", 2:"Chelsea", 3:"Liverpool",
        4:"Manchester City", 5:"Manchester United",
        6:"Tottenham Hotspur", 99:"Other Team"
    }
    def name_by_id(tid: int) -> str:
        return teams_map.get(tid, {}).get("name") or DEFAULT_TEAM_NAMES.get(tid, str(tid))

    # ----- layout ของตาราง -----
    HDRS   = ["TID","Player_ID","Player","from_Team","to_Team","Age","Fee(M)","Position","Status","Active","Date"]
    WIDTHS = [   5,        10,      20,        18,       18,    5,     8,        9,        8,       8,     12]    

    def _sep():
        # เส้นคั่นตามความกว้างจริงของคอลัมน์
        return "+" + "+".join("-"*(w+2) for w in WIDTHS) + "+\n"

    def _hdr():
        # แถวหัวคอลัมน์ จัดกึ่งกลาง
        return "| " + " | ".join(f"{h:^{w}}" for h, w in zip(HDRS, WIDTHS)) + " |\n"

    with open(report_file, "w", encoding="utf-8") as f:
        # ----- Header -----
        f.write("Big 6 Transfer Market - (Summary Report)\n")
        f.write(f"Generated at : {dt.datetime.now():%Y-%m-%d %H:%M:%S} (+07:00)\n")
        f.write("App version  : 1.0\n")
        f.write("Endianness   : Little-Endian\n")
        f.write("Encoding     : UTF-8 (Fixed-Length)\n\n")

        # ----- Transfer Table -----
        f.write("+----------------+\n| Transfer Table |\n+----------------+\n\n")
        f.write(_sep())
        f.write(_hdr())
        f.write(_sep())

        for t in transfers:
            p = players_map.get(t["player_id"])
            pname = (p["name"] if p else "-")[:WIDTHS[2]]
            pos   = (p["pos"] if p else "-")
            from_name = name_by_id(t["from"])[:WIDTHS[3]]
            to_name   = name_by_id(t["to"])[:WIDTHS[4]]
            dstr = yyyymmdd_to_str(t["date"])

            cells = [
                f"{t['id']:<{WIDTHS[0]}}",
                f"{t['player_id']:<{WIDTHS[1]}}",
                f"{pname:<{WIDTHS[2]}}",
                f"{from_name:<{WIDTHS[3]}}",
                f"{to_name:<{WIDTHS[4]}}",
                f"{t['age']:<{WIDTHS[5]}}",
                f"{t['price']:{WIDTHS[6]}.1f}",  
                f"{pos:^{WIDTHS[7]}}",
                f"{str(t['status']):<{WIDTHS[8]}}",
                f"{str(t['active']):<{WIDTHS[9]}}",
                f"{dstr:<{WIDTHS[10]}}",
            ]
            f.write("| " + " | ".join(cells) + " |\n")

        f.write(_sep())
        f.write("\n")

        # ----- Summary (Active Player) -----
        act_players = [p for p in players if p["active"]]
        vals = [p["price"] for p in act_players]
        f.write("Summary (Active Player)\n")
        f.write(f"- Total Player : {len(players)}\n")
        f.write(f"- Active Players: {len(act_players)}\n")
        f.write(f"- Deleted Player: {len(players) - len(act_players)}\n")
        if vals:
            f.write(f"- Average ValueM: {sum(vals)/len(vals):.1f}\n")
            f.write(f"- Max ValueM : {max(vals):.1f}\n")
            f.write(f"- Min ValueM : {min(vals):.1f}\n")
        f.write("\n")

        # ----- Transfer (Active Only) -----
        act_trans = [t for t in transfers if t["active"]]
        fees = [t["price"] for t in act_trans]
        f.write("Transfer (Active Only)\n")
        f.write(f"- Total Transfer: {len(act_trans)}\n")
        if fees:
            f.write(f"- Highest Fee : {max(fees):.1f}\n")
            f.write(f"- Lowest Fee  : {min(fees):.1f}\n")
            f.write(f"- Average Fee : {sum(fees)/len(fees):.1f}\n")

# ===============================
# Menus
# ===============================
def main_menu():
    while True:
        print("\n================ BIG 6 TRANSFER MARKET ================")
        print("1) Add Player")
        print("2) Update Player")
        print("3) Delete Player")
        print("4) View Players")
        print("5) Add Transfer")
        print("6) View Transfers")
        print("7) Generate Report")
        print("0) Exit")
        print("=======================================================")

        choice = input("เลือกเมนู: ").strip()

        if choice == "1":
            try:
                pid = int(input("Player ID: ").strip())
                ensure_unique_player_id(pid)
                name = input("Name: ").strip()
                pos  = require_position(input("Position (FW/MF/DF/GK/...): ").strip())
                age  = int(input("Age: ").strip())
                price= float(input("Price Buy (ล้าน): ").strip())
                team = require_team_id(int(input("Team ID (1-6 หรือ 99=OTH): ").strip()))
                add_player(pid, name, pos, age, price, team, active=True)
                print("✔ เพิ่ม Player สำเร็จ")
            except Exception as e:
                print(f"❌ {e}")

        elif choice == "2":
            try:
                pid = int(input("Player ID ที่จะแก้ไข: ").strip())
                cur = find_player(pid)
                if not cur:
                    print("❌ ไม่พบ Player ID นี้");  continue
                new_name = input(f"Name ใหม่ (Enter = {cur['name']}): ").strip()
                new_pos  = input(f"Position ใหม่ (Enter = {cur['pos']}): ").strip()
                new_age  = input(f"Age ใหม่ (Enter = {cur['age']}): ").strip()
                new_price= input(f"Price ใหม่ (Enter = {fmt_money(cur['price'])}): ").strip()
                new_team = input(f"Team ID ใหม่ (Enter = {cur['team_id']}): ").strip()

                nd = {}
                if new_name: nd["name"] = new_name
                if new_pos:  nd["pos"]  = require_position(new_pos)
                if new_age:  nd["age"]  = int(new_age)
                if new_price:nd["price"]= float(new_price)
                if new_team: nd["team_id"]= require_team_id(int(new_team))
                update_player(pid=pid, new_data=nd)
                print("✔ แก้ไข Player สำเร็จ")
            except Exception as e:
                print(f"❌ {e}")

        elif choice == "3":
            pid = int(input("Player ID ที่จะลบ: ").strip())
            target = find_player(pid)
            if not target: print("❌ ไม่พบ Player ID นี้");  continue
            if not target["active"]: print("ℹ️ ผู้เล่นนี้ถูกลบอยู่แล้ว");  continue
            cf = input(f"ยืนยันลบ {target['name']} (ID {pid}) ? [y/N]: ").strip().lower()
            if cf == "y":
                update_player(pid=pid, new_data={"active": False})
                print("✔ ลบ Player (Soft Delete)")
            else:
                print("ยกเลิก")

        elif choice == "4":
            teams = get_team_map()
            print("\nID   Name                     Pos Age  Price   Team (fullname)        Active")
            print("---------------------------------------------------------------------------------")
            for p in read_players():
                tname = team_name_by_id(p["team_id"], teams)
                print(f"{p['id']:<4} {p['name']:<23} {p['pos']:<3} {p['age']:<3} {fmt_money(p['price']):>7}   {tname:<22} {p['active']}")

        elif choice == "5":
            try:
                tid = int(input("Transfer ID: ").strip())
                ensure_unique_transfer_id(tid)
                pid = int(input("Player ID: ").strip())
                ply = find_player(pid)
                if not ply:             raise ValueError("ไม่พบ Player ID นี้")
                if not ply["active"]:   raise ValueError("ผู้เล่น inactive — ห้ามทำ Transfer")
                from_id = require_team_id(int(input("From Team ID: ").strip()))
                to_id   = require_team_id(int(input("To Team ID: ").strip()))
                if from_id == to_id:    raise ValueError("from/to ต้องต่างกัน")
                if ply["team_id"] != from_id:
                    raise ValueError(f"from_team_id ต้องตรงกับทีมปัจจุบันของผู้เล่น (current={ply['team_id']})")
                age   = int(input("Age ตอนขาย: ").strip())
                price = float(input("Fee (ล้าน): ").strip())
                date  = int(input("Date (YYYYMMDD): ").strip())
                add_transfer(tid, pid, from_id, to_id, age, price, date, status=True, active=True)
                print("✔ เพิ่ม Transfer สำเร็จ")
            except Exception as e:
                print(f"❌ {e}")

        elif choice == "6":
            rows = read_transfers()
            players = {p["id"]: p for p in read_players()}
            teams_map = get_team_map()
            print("\nID    Player_ID  Player Name         From (fullname)     To (fullname)       Age  Fee(M)  Pos    Status Active   Date")
            print("-------------------------------------------------------------------------------------------------------------------------")
            for t in rows:
                p = players.get(t["player_id"])
                pname = p["name"] if p else "-"
                pos   = (p["pos"] if p else "-").center(6)
                from_name = team_name_by_id(t["from"], teams_map)
                to_name   = team_name_by_id(t["to"], teams_map)
                print(f"{t['id']:<6}{t['player_id']:<11}{pname:<20}{from_name:<20}{to_name:<20}"
                    f"{t['age']:<5}{fmt_money(t['price']):>7}  {pos}  {str(t['status']):<6} {str(t['active']):<6}  {t['date']}")

        elif choice == "7":
            generate_report()
            print("✔ สร้างรายงาน summary.txt สำเร็จ")

        elif choice == "0":
            print("👋 ออกโปรแกรมเรียบร้อย")
            break
        else:
            print("❌ เมนูไม่ถูกต้อง ลองใหม่อีกครั้ง")

if __name__ == "__main__":
    main_menu()
