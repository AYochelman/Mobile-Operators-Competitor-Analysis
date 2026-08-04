import React, {useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowLeft, BadgeCheck, ChevronDown, CircleDollarSign, Globe2, Menu, Search, ShieldCheck, Signal, Sparkles, TrendingDown, Wifi, X} from 'lucide-react';
import './style.css';

const plans = [
  {carrier:'wecom',logo:'W',color:'#6757ff',name:'Free 5G',gb:300,price:29.9,tag:'הכי משתלם',note:'מחיר קבוע לשנה'},
  {carrier:'Partner',logo:'P',color:'#f25a78',name:'Power 5G',gb:500,price:39.9,tag:'הכי פופולרי',note:'כולל 5G'},
  {carrier:'Cellcom',logo:'C',color:'#6b45cc',name:'MAX Family',gb:400,price:34.9,tag:'למשפחות',note:'בהצטרפות 2 קווים'},
  {carrier:'Pelephone',logo:'p',color:'#1299df',name:'Ultra 5G',gb:1000,price:49.9,tag:'הכי הרבה גלישה',note:'כולל גלישה בחו״ל'},
  {carrier:'HOT mobile',logo:'H',color:'#e52a2a',name:'TOP 5G',gb:250,price:32.9,tag:'מחיר מצוין',note:'דקות והודעות ללא הגבלה'},
  {carrier:'Golan',logo:'G',color:'#08a9a6',name:'Golan 750',gb:750,price:46,tag:'חבילת פרימיום',note:'אפליקציות ללא הגבלה'}
];

function App(){
  const [tab,setTab]=useState('סלולר בישראל'); const [query,setQuery]=useState(''); const [max,setMax]=useState(60); const [menu,setMenu]=useState(false);
  const filtered=useMemo(()=>plans.filter(p=>(p.carrier+p.name).toLowerCase().includes(query.toLowerCase())&&p.price<=max),[query,max]);
  return <div dir="rtl">
    <header><a className="brand" href="#"><span className="mark"><Signal size={22}/></span><span>MOCA</span><small>משווים. חוסכים.</small></a>
      <nav><a href="#plans">השוואת חבילות</a><a href="#how">איך זה עובד</a><a href="#why">למה MOCA</a><a href="#faq">שאלות נפוצות</a></nav>
      <button className="login">כניסה למערכת <ArrowLeft size={16}/></button><button className="hamb" onClick={()=>setMenu(!menu)}>{menu?<X/>:<Menu/>}</button>
      {menu&&<div className="mobile"><a href="#plans">השוואת חבילות</a><a href="#how">איך זה עובד</a><a href="#why">למה MOCA</a></div>}
    </header>
    <main>
      <section className="hero">
        <div className="halo one"/><div className="halo two"/>
        <div className="eyebrow"><Sparkles size={15}/> כל חבילות הסלולר במקום אחד</div>
        <h1>מוצאים את החבילה<br/><em>שבאמת מתאימה לכם</em></h1>
        <p>משווים מחירים, נפחי גלישה והטבות מכל חברות הסלולר וה‑eSIM. מידע ברור, מעודכן וללא אותיות קטנות.</p>
        <div className="tabs">{['סלולר בישראל','גלישה בחו״ל','eSIM גלובלי'].map((t,i)=><button className={tab===t?'active':''} onClick={()=>setTab(t)} key={t}>{i===0?<Signal/>:i===1?<Globe2/>:<Wifi/>}{t}</button>)}</div>
        <div className="finder"><div><label>מה מחפשים?</label><span><Search size={19}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="חברה או שם חבילה"/></span></div><div><label>תקציב חודשי</label><select value={max} onChange={e=>setMax(+e.target.value)}><option value="40">עד ₪40</option><option value="60">עד ₪60</option><option value="100">עד ₪100</option></select></div><button onClick={()=>document.querySelector('#plans').scrollIntoView({behavior:'smooth'})}>מצאו לי חבילה <ArrowLeft/></button></div>
        <div className="trust"><span><BadgeCheck/> מידע מעודכן מדי יום</span><span><ShieldCheck/> השוואה אובייקטיבית</span><span><CircleDollarSign/> ללא עלות</span></div>
      </section>

      <section className="plans" id="plans"><div className="section-head"><div><span className="kicker">השוואה חכמה</span><h2>החבילות המומלצות עכשיו</h2><p>{tab} · נמצאו {filtered.length} חבילות בתקציב שלך</p></div><button className="sort">מיון לפי מחיר <ChevronDown/></button></div>
        <div className="grid">{filtered.map((p,i)=><article className={i===0?'featured':''} key={p.name}>{i===0&&<div className="ribbon">הבחירה של MOCA</div>}<div className="cardtop"><span className="logo" style={{background:p.color}}>{p.logo}</span><div><b>{p.carrier}</b><small>{p.name}</small></div><span className="tag">{p.tag}</span></div><div className="data"><div><strong>{p.gb}</strong><span>GB</span><small>גלישה</small></div><div className="divider"/><div><strong>5G</strong><small>מהירות</small></div><div className="divider"/><div><strong>∞</strong><small>דקות ו‑SMS</small></div></div><div className="note"><BadgeCheck/>{p.note}</div><div className="price"><div><span>₪</span><strong>{p.price}</strong><small>לחודש</small></div><button>לפרטי החבילה <ArrowLeft/></button></div></article>)}</div>
        {filtered.length===0&&<div className="empty">לא מצאנו חבילות בטווח הזה. נסו להגדיל את התקציב.</div>}
      </section>

      <section className="how" id="how"><span className="kicker">פשוט וחכם</span><h2>שלושה צעדים לחיסכון קבוע</h2><div className="steps"><div><i>1</i><Search/><h3>בוחרים מה חשוב</h3><p>תקציב, גלישה, 5G והטבות שאתם באמת צריכים.</p></div><div><i>2</i><TrendingDown/><h3>משווים בשקיפות</h3><p>רואים את כל האפשרויות זו לצד זו, בלי רעש.</p></div><div><i>3</i><BadgeCheck/><h3>עוברים בביטחון</h3><p>נכנסים להצעה המתאימה ומצטרפים ישירות לספק.</p></div></div></section>
      <section className="why" id="why"><div><span className="kicker">למה MOCA</span><h2>פחות זמן בחיפושים.<br/>יותר כסף שנשאר אצלכם.</h2><p>אנחנו סורקים עשרות ספקים ומציגים את הפרטים החשובים בפורמט אחיד שקל להבין.</p><ul><li><BadgeCheck/> מחירים ותנאים שמתעדכנים באופן שוטף</li><li><BadgeCheck/> חבילות סלולר, נדידה ו‑eSIM במקום אחד</li><li><BadgeCheck/> סינון חכם לפי הצורך האמיתי שלכם</li></ul></div><div className="saving"><small>החיסכון השנתי הפוטנציאלי</small><strong>₪624</strong><span>בהשוואה לחבילה ממוצעת יקרה יותר</span><div className="bars"><i/><i/><i/><i/><i/></div></div></section>
    </main>
    <footer><a className="brand"><span className="mark"><Signal size={20}/></span><span>MOCA</span></a><p>השוואת סלולר חכמה, פשוטה ושקופה.</p><span>© 2026 MOCA</span></footer>
  </div>
}
createRoot(document.getElementById('root')).render(<App/>);
