"""مغز v1.0 — عامل هوشمند با حافظه ساخت‌یافته؛ هسته قابل استفاده در Cloud."""
import sqlite3, uuid, json, os
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat()

class Brain:
    def __init__(self, db_path=None):
        db_path = db_path or os.getenv("BRAIN_DB_PATH", "brain.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        c=self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,type TEXT,name TEXT,aliases TEXT,data TEXT,valid_from TEXT,valid_to TEXT,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS relations(id TEXT PRIMARY KEY,src TEXT,dst TEXT,rel TEXT,data TEXT,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,entity_id TEXT,kind TEXT,payload TEXT,timestamp TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY,entity_id TEXT,text TEXT,confidence REAL,source TEXT,evidence TEXT,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY,title TEXT,options TEXT,chosen TEXT,rationale TEXT,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS outcomes(id TEXT PRIMARY KEY,decision_id TEXT,result TEXT,score REAL,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS learning(id TEXT PRIMARY KEY,decision_id TEXT,outcome_id TEXT,lesson TEXT,created_at TEXT)""")
        self.conn.commit()

    def register(self,type_,name,aliases=None,data=None):
        existing=self.resolve(name)
        if existing: return existing
        eid=str(uuid.uuid4()); t=now()
        self.conn.execute("INSERT INTO entities VALUES(?,?,?,?,?,?,?,?)",(eid,type_,name,json.dumps(aliases or [],ensure_ascii=False),json.dumps(data or {},ensure_ascii=False),t,None,t))
        self.conn.commit(); self._event(eid,"created",{"name":name,"type":type_})
        return eid

    def resolve(self,name):
        name_l=name.strip().casefold()
        for row in self.conn.execute("SELECT * FROM entities"):
            if row["name"].strip().casefold()==name_l: return row["id"]
            try: aliases=[a.casefold() for a in json.loads(row["aliases"] or "[]")]
            except (TypeError,ValueError): aliases=[]
            if name_l in aliases: return row["id"]
        return None

    def dedup(self,id_keep,id_drop):
        self.conn.execute("UPDATE relations SET src=? WHERE src=?",(id_keep,id_drop))
        self.conn.execute("UPDATE relations SET dst=? WHERE dst=?",(id_keep,id_drop))
        self.conn.execute("UPDATE claims SET entity_id=? WHERE entity_id=?",(id_keep,id_drop))
        self.conn.execute("UPDATE events SET entity_id=? WHERE entity_id=?",(id_keep,id_drop))
        self.conn.execute("DELETE FROM entities WHERE id=?",(id_drop,)); self.conn.commit()
        self._event(id_keep,"dedup_merged",{"dropped":id_drop})

    def relate(self,src,dst,rel,data=None):
        rid=str(uuid.uuid4())
        self.conn.execute("INSERT INTO relations VALUES(?,?,?,?,?,?)",(rid,src,dst,rel,json.dumps(data or {},ensure_ascii=False),now()))
        self.conn.commit(); return rid

    def _event(self,entity_id,kind,payload):
        self.conn.execute("INSERT INTO events VALUES(?,?,?,?,?)",(str(uuid.uuid4()),entity_id,kind,json.dumps(payload,ensure_ascii=False),now()))
        self.conn.commit()

    def history(self,entity_id):
        return [dict(r) for r in self.conn.execute("SELECT * FROM events WHERE entity_id=? ORDER BY timestamp",(entity_id,))]

    def claim(self,entity_id,text,source="unknown",evidence=None,confidence=0.5):
        confidence=max(0.0,min(1.0,float(confidence)))
        cid=str(uuid.uuid4())
        self.conn.execute("INSERT INTO claims VALUES(?,?,?,?,?,?,?)",(cid,entity_id,text,confidence,source,json.dumps(evidence or [],ensure_ascii=False),now()))
        self.conn.commit(); return cid

    def detect_contradiction(self,entity_id):
        rows=list(self.conn.execute("SELECT text FROM claims WHERE entity_id=?",(entity_id,)))
        texts=[r["text"] for r in rows]; conflicts=[]
        neg=("نکرد","نیست","نشد","ندارد","عدم","not ","no ")
        for i,a in enumerate(texts):
            for b in texts[i+1:]:
                al,bl=a.casefold(),b.casefold()
                if (al in bl and any(n in bl for n in neg)) or (bl in al and any(n in al for n in neg)):
                    conflicts.append((a,b))
        return conflicts

    def decide(self,title,options,chosen,rationale=""):
        did=str(uuid.uuid4())
        self.conn.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?)",(did,title,json.dumps(options,ensure_ascii=False),chosen,rationale,now()))
        self.conn.commit(); return did

    def outcome(self,decision_id,result,score):
        oid=str(uuid.uuid4()); score=float(score)
        self.conn.execute("INSERT INTO outcomes VALUES(?,?,?,?,?)",(oid,decision_id,result,score,now()))
        lesson=f"score={score} → {'موفق' if score>0.6 else 'نیاز به بازبینی'}"
        self.conn.execute("INSERT INTO learning VALUES(?,?,?,?,?)",(str(uuid.uuid4()),decision_id,oid,lesson,now()))
        self.conn.commit(); return oid

    def reason(self,entity_id):
        e=self.conn.execute("SELECT * FROM entities WHERE id=?",(entity_id,)).fetchone()
        if not e: return ["موجودیت یافت نشد"]
        rels=list(self.conn.execute("SELECT * FROM relations WHERE src=? OR dst=?",(entity_id,entity_id)))
        claims=list(self.conn.execute("SELECT * FROM claims WHERE entity_id=?",(entity_id,)))
        confs=[c["confidence"] for c in claims] or [0]
        steps=[f"موجودیت: {e['name']} ({e['type']})",f"روابط: {len(rels)}",f"ادعاها: {len(claims)}",f"میانگین اطمینان ادعاها: {sum(confs)/len(confs):.2f}"]
        contra=self.detect_contradiction(entity_id)
        if contra: steps.append(f"تناقض‌های احتمالی: {len(contra)}")
        return steps

    def solve(self,entity_id):
        steps=self.reason(entity_id)
        claims=list(self.conn.execute("SELECT * FROM claims WHERE entity_id=? ORDER BY confidence DESC",(entity_id,)))
        if not claims: return {"answer":"شواهد کافی نیست","confidence":0.0,"trace":steps,"status":"insufficient_evidence"}
        best=claims[0]
        return {"answer":best["text"],"confidence":best["confidence"],"trace":steps,"status":"candidate_requires_verification","source":best["source"]}

    def stats(self):
        return {table:self.conn.execute("SELECT COUNT(*) FROM "+table).fetchone()[0] for table in ("entities","relations","events","claims","decisions","outcomes","learning")}
