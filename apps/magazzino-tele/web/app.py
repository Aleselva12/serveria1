"""Standalone Magazzino Tele web application. No Cora imports or AI integrations."""
import os
from flask import Flask, abort, jsonify, render_template_string, request
import mysql.connector

app = Flask(__name__)
TABLES = {
    "clienti": "customers",
    "colori": "schema colori semplice",
    "prodotti": "prodotti_completi",
    "modelli": "modelli",
    "ordini": "ordini",
    "righe_ordine": "ordiniprodotti",
    "magazzino": "magazzino",
}
HTML = """
<!doctype html><html lang="it"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Magazzino Tele</title><style>
body{font-family:system-ui,Arial;margin:0;background:#f6f7f9;color:#17212c}
header{background:#172c42;color:white;padding:18px 24px}h1{font-size:23px;margin:0}
nav{display:flex;gap:7px;flex-wrap:wrap;padding:14px 24px;background:white;border-bottom:1px solid #ddd}
button,input{font:inherit;padding:9px;border:1px solid #bcc6cf;border-radius:5px}
button{cursor:pointer;background:white}button.active,.primary{background:#155b96;color:white}
main{padding:20px 24px}.tools{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px}
table{width:100%;border-collapse:collapse;background:white;font-size:14px}
th,td{border:1px solid #dce1e6;padding:9px;text-align:left;vertical-align:top}
th{background:#eaf0f6;white-space:nowrap}td{max-width:260px;overflow-wrap:anywhere}
.scroll{overflow:auto;max-height:68vh}#notice{white-space:pre-wrap;margin:10px 0}
dialog{border:1px solid #ccd3dc;border-radius:8px;max-height:85vh;overflow:auto;width:min(95vw,640px)}
.field{display:grid;gap:4px;margin:9px 0}.field input{width:97%}
.actions{display:flex;gap:8px;margin-top:18px}
</style>
<header><h1>Magazzino Tele</h1>Gestionale indipendente</header><nav id="tabs"></nav>
<main><div class="tools"><input id="q" placeholder="Cerca nei risultati" aria-label="Cerca">
<button onclick="refresh()">Aggiorna</button><button class="primary" onclick="edit(null)">Nuovo</button></div>
<div id="notice"></div><div class="scroll"><table><thead id="head"></thead><tbody id="body"></tbody></table></div>
<div style="margin-top:12px"><button onclick="page=Math.max(0,page-1);refresh()">Precedenti</button>
<span id="pages"></span> <button onclick="page++;refresh()">Successivi</button></div></main>
<dialog id="editor"><h2 id="editTitle">Modifica</h2><form id="form"></form>
<div class="actions"><button class="primary" onclick="save()">Salva</button>
<button onclick="document.getElementById('editor').close()">Annulla</button>
<button id="deleteBtn" onclick="removeRow()">Elimina</button></div></dialog>
<script>
const tabs=['clienti','colori','prodotti','modelli','ordini','righe_ordine','magazzino'];
let current='ordini',page=0,cols=[],pk=[],rows=[],editing=null;
const tabsEl=document.getElementById('tabs'),head=document.getElementById('head'),body=document.getElementById('body');
function text(el,value){el.textContent=value==null?'':String(value)}
tabs.forEach(name=>{const b=document.createElement('button');text(b,name.replace('_',' '));b.onclick=()=>{current=name;page=0;refresh()};b.id='tab-'+name;tabsEl.appendChild(b)});
async function api(path,options){const r=await fetch('/api/'+path,options);const data=await r.json();if(!r.ok)throw Error(data.error||'Errore');return data}
function message(s){text(document.getElementById('notice'),s)}
async function refresh(){
 try{const data=await api(current+'?page='+page+'&q='+encodeURIComponent(document.getElementById('q').value));
 cols=data.columns;pk=data.pk;rows=data.rows;head.replaceChildren();body.replaceChildren();
 tabs.forEach(t=>document.getElementById('tab-'+t).classList.toggle('active',t===current));
 const tr=document.createElement('tr');for(const c of cols){const th=document.createElement('th');text(th,c);tr.appendChild(th)}
 const th=document.createElement('th');text(th,'Azioni');tr.appendChild(th);head.appendChild(tr);
 for(const row of rows){const tr=document.createElement('tr');cols.forEach(c=>{const td=document.createElement('td');text(td,row[c]);tr.appendChild(td)});
 const td=document.createElement('td');const b=document.createElement('button');text(b,'Modifica');b.onclick=()=>edit(row);td.appendChild(b);tr.appendChild(td);body.appendChild(tr)}
 text(document.getElementById('pages'),'Pagina '+(page+1)+' — '+rows.length+' risultati');
 message(data.warning||'');}
 catch(e){message(e.message);head.replaceChildren();body.replaceChildren()}
}
function edit(row){editing=row;const form=document.getElementById('form');form.replaceChildren();
 text(document.getElementById('editTitle'),row?'Modifica':'Nuovo elemento');
 cols.forEach(col=>{const label=document.createElement('label');label.className='field';text(label,col);
 const inp=document.createElement('input');inp.name=col;inp.value=row&&row[col]!=null?row[col]:'';inp.disabled=!!row&&pk.includes(col);
 label.appendChild(inp);form.appendChild(label)});
 document.getElementById('deleteBtn').hidden=!row||!pk.length;
 document.getElementById('editor').showModal()}
function payload(){const out={};new FormData(document.getElementById('form')).forEach((v,k)=>{out[k]=v===''?null:v});return out}
function key(){const k={};pk.forEach(c=>k[c]=editing[c]);return k}
async function save(){try{
 const updating=!!editing;if(updating&&!pk.length)throw Error('Tabella senza chiave primaria: modifica disabilitata');
 await api(current+(updating?'/row':''),{method:updating?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(updating?{key:key(),values:payload()}:{values:payload()})});
 document.getElementById('editor').close();await refresh()
 }catch(e){message(e.message)}}
async function removeRow(){if(!pk.length||!confirm('Eliminare definitivamente questo record?'))return;
 try{await api(current+'/row',{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:key()})});
 document.getElementById('editor').close();await refresh()}catch(e){message(e.message)}}
document.getElementById('q').addEventListener('change',()=>{page=0;refresh()});refresh()
</script></html>
"""
def db():
    return mysql.connector.connect(host=os.environ["TELE_DB_HOST"],
        port=int(os.environ.get("TELE_DB_PORT","3306")),
        database=os.environ.get("TELE_DB_NAME","magazzino_tele"),
        user=os.environ["TELE_DB_USER"],password=os.environ["TELE_DB_PASSWORD"],
        charset="utf8mb4",connection_timeout=5)
def ident(name):
    return "`"+name.replace("`","``")+"`"
def schema(cur,table):
    cur.execute("SELECT COLUMN_NAME, COLUMN_KEY, EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",(table,))
    data=cur.fetchall()
    if not data:abort(404,"Tabella non presente nel database")
    return [x[0] for x in data],[x[0] for x in data if x[1]=="PRI"],[x[0] for x in data if "auto_increment" in x[2]]
def managed(alias):
    if alias not in TABLES:abort(404)
    return TABLES[alias]
@app.errorhandler(Exception)
def fail(err):
    from werkzeug.exceptions import HTTPException
    return jsonify(error=err.description if isinstance(err,HTTPException) else "Errore nell'operazione sul database"),getattr(err,"code",500)
@app.get("/")
def index():return render_template_string(HTML)
@app.get("/health")
def health():
    conn=db()
    try:
        cur=conn.cursor();cur.execute("SELECT 1");cur.fetchone()
        return jsonify(status="ok")
    finally:conn.close()
@app.get("/api/<alias>")
def list_rows(alias):
    table=managed(alias);page=min(max(int(request.args.get("page","0")),0),10000)
    q=request.args.get("q","")[:120]
    conn=db()
    try:
        cur=conn.cursor();columns,pk,auto=schema(cur,table)
        searchable=[c for c in columns if c not in auto]
        where=(" WHERE "+" OR ".join("CAST("+ident(c)+" AS CHAR) LIKE %s" for c in searchable)) if q and searchable else ""
        args=(["%"+q+"%"]*len(searchable)) if where else []
        order=" ORDER BY "+",".join(ident(c) for c in pk) if pk else ""
        cur.execute("SELECT * FROM "+ident(table)+where+order+" LIMIT 50 OFFSET %s",args+[page*50])
        rows=[dict(zip([d[0] for d in cur.description],(None if v is None else str(v) for v in row))) for row in cur.fetchall()]
        return jsonify(columns=columns,pk=pk,rows=rows,warning="" if pk else "Nessuna chiave primaria: aggiornamento e cancellazione non disponibili")
    finally:conn.close()
def write(alias,operation):
    table=managed(alias);body=request.get_json(silent=True) or {}
    conn=db()
    try:
        cur=conn.cursor();cols,pk,auto=schema(cur,table);values=body.get("values",{})
        if not isinstance(values,dict) or any(k not in cols for k in values):abort(400,"Campi non validi")
        if operation=="create":
            writable={k:v for k,v in values.items() if k not in auto}
            if not writable:abort(400,"Nessun campo fornito")
            sql="INSERT INTO "+ident(table)+" ("+",".join(map(ident,writable))+") VALUES ("+",".join(["%s"]*len(writable))+")"
            cur.execute(sql,list(writable.values()))
        else:
            key=body.get("key",{})
            if not pk or not isinstance(key,dict) or set(key)!=set(pk):abort(400,"Chiave primaria mancante")
            where=" AND ".join(ident(k)+"=%s" for k in pk)
            if operation=="delete":
                cur.execute("DELETE FROM "+ident(table)+" WHERE "+where,[key[k] for k in pk])
            else:
                writable={k:v for k,v in values.items() if k not in pk and k not in auto}
                if not writable:abort(400,"Nessun campo aggiornabile")
                cur.execute("UPDATE "+ident(table)+" SET "+",".join(ident(k)+"=%s" for k in writable)+" WHERE "+where,list(writable.values())+[key[k] for k in pk])
        conn.commit();return jsonify(ok=True,affected=cur.rowcount)
    except Exception:
        conn.rollback();raise
    finally:conn.close()
@app.post("/api/<alias>")
def create(alias):return write(alias,"create")
@app.patch("/api/<alias>/row")
def update(alias):return write(alias,"update")
@app.delete("/api/<alias>/row")
def delete(alias):return write(alias,"delete")
if __name__=="__main__":
    app.run(host="127.0.0.1",port=8082)
