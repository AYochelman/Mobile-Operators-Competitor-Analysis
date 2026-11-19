// Ski destinations for the "גלישה לגולשים" tab (/ski).
//
// Resort list = the resorts WeSki sells (https://www.weski.com/ski-resorts,
// collected 2026-11-19: 308 resorts in 20 countries). Refresh by re-reading the
// per-country pages there; a resort only needs its country to be right, because
// every provider sells coverage per COUNTRY, never per resort.
//
// `he` must be the canonical Hebrew country name used by globalCountries.js /
// abroadCountries.js (matching goes through destKey, so spelling variants that
// resolve to the same English are fine).

const split = (s) => s.split(';').map(x => x.trim()).filter(Boolean)

export const SKI_COUNTRIES = [
  { id: 'france', he: 'צרפת', en: 'France', resorts: split(
    "Tignes; Val Thorens; Les Arcs; Alpe d'Huez; Avoriaz; Méribel; Morzine; Les Menuires; Les Deux Alpes; Chamonix; Flaine; Val d'Isère; Megève; La Plagne; La Rosière; Les Gets; Saint Gervais Les Bains; La Clusaz; Courchevel; Serre Chevalier; La Tania; Samoëns; Montgenèvre; Vaujany; Valmorel; Les Carroz; Val Cenis; Le Grand-Bornand; St Martin de Belleville; Peisey-Vallandry; Brides-Les-Bains; Chamrousse; Les Houches; Les Saisies; Galibier-Thabor; Morillon; Châtel; Risoul; Les Orres; Isola 2000; Font-Romeu Pyrenees; Les Contamines-Montjoie; Pralognan-La-Vanoise; La Toussuire; Champagny-En-Vanoise; Les Angles; Super Besse; La Mongie - Grand Tourmalet; La Bresse - Hohneck; Saint Lary Soulan; Le Lioran; Ax Les Thermes; St Francois Longchamp; Le Corbier; Les Allues; Peyragudes; St Jean D'Aulps; Saint Sorlin d'Arves; Auron; Sainte Foy; Pra Loup; Valfrejus; Orcieres; Areches-Beaufort; Vars") },
  { id: 'austria', he: 'אוסטריה', en: 'Austria', resorts: split(
    'Obergurgl-Hochgurgl; Seefeld; Saalbach; Kaprun; Zell am See; Mayrhofen; Bad Gastein; St. Anton; Ischgl; Söll; Kitzbühel; Sölden; Lech Zürs; Alpbach; Obertauern; Serfaus; Flachau; Schladming; Bad Hofgastein; Hinterglemm; St Johann In Tirol; Ellmau; Kaltenbach; Tux; Silvretta Montafon; Niederau; Kappl; Westendorf; Wagrain; St Johann Im Pongau; Fieberbrunn; Kuhtai; Gerlos; Rauris; Neustift - Fulpmes; Kirchberg; Hopfgarten; Grossarl; Pitztal; Muhlbach Am Hochkönig; Königsleiten; Axamer Lizum - Muttereralm; Jochberg; Maria Alm; Galtur; Nassfeld - Mokrine; Brixen im Thale; Heiligenblut; Annaberg Im Lammertal; Kleinarl; Scheffau; Waidring; Leogang') },
  { id: 'italy', he: 'איטליה', en: 'Italy', resorts: split(
    "Sestriere; Sauze D'Oulx; Val Gardena; Livigno; Breuil-Cervinia; Alta Badia; Courmayeur; Bardonecchia; Madonna di Campiglio; Pila; Cortina d'Ampezzo; Passo Tonale; La Thuile; Canazei; Campitello di Fassa; Kronplatz; Val di Sole; Bormio; Champoluc; Pinzolo; Val di Fiemme; Sansicario - Cesana; Arabba; Ponte Di Legno; Aprica; Civetta; San Candido; Mondole Ski; Claviere; Alagna Valsesia; Folgaria; Alpe di Siusi; Paganella - Andalo; Falcade; Ravascletto - Zoncolan; Madesimo; Sesto; San Martino di Castrozza; Moena-Alpe Lusia-Bellamonte; Riserva Bianca") },
  { id: 'switzerland', he: 'שוויץ', en: 'Switzerland', resorts: split(
    'Zermatt; Verbier; Grindelwald; Saas Fee; St. Moritz; Crans-Montana; Nendaz; Laax; Wengen; Davos; Villars; Engelberg; Andermatt; Arosa; Gstaad; Lenzerheide; Les Crosets; Thyon-Les Collons; Samnaun; Zinal; Klosters; Champoussin; Morgins; La Tzoumaz; Champery') },
  { id: 'andorra', he: 'אנדורה', en: 'Andorra', resorts: split(
    'Pas de la Casa; Arinsal; Soldeu; El Tarter; Encamp; Canillo; Ordino') },
  { id: 'bulgaria', he: 'בולגריה', en: 'Bulgaria', resorts: split('Bansko; Borovets; Pamporovo') },
  { id: 'georgia', he: 'גאורגיה', en: 'Georgia', resorts: split('Gudauri') },
  { id: 'germany', he: 'גרמניה', en: 'Germany', resorts: split(
    'Garmisch-Partenkirchen; Balderschwang; Spitzingsee; Oberstdorf; Brauneck') },
  { id: 'spain', he: 'ספרד', en: 'Spain', resorts: split('Sierra Nevada; Baqueira-Beret') },
  { id: 'poland', he: 'פולין', en: 'Poland', resorts: split('Zakopane; Bialka Tatrzanska; Szczyrk') },
  { id: 'slovakia', he: 'סלובקיה', en: 'Slovakia', resorts: split('Jasna Nizke Tatry; Tatranska Lomnica') },
  { id: 'slovenia', he: 'סלובניה', en: 'Slovenia', resorts: split('Kranjska Gora; Vogel; Maribor Pohorje') },
  { id: 'bosnia', he: 'בוסניה והרצגובינה', en: 'Bosnia and Herzegovina', resorts: split('Jahorina') },
  { id: 'norway', he: 'נורבגיה', en: 'Norway', resorts: split(
    'Trysil; Geilo; Voss; Hemsedal; Hafjell; Kvitfjell; Gausta') },
  { id: 'sweden', he: 'שבדיה', en: 'Sweden', resorts: split('Salen') },
  { id: 'finland', he: 'פינלנד', en: 'Finland', resorts: split('Ruka; Levi; Yllas; Salla; Pyha') },
  { id: 'usa', he: 'ארצות הברית', en: 'United States', resorts: split(
    'Breckenridge; Aspen Snowmass; Vail; Park City; Keystone; Beaver Creek; Jackson Hole; Deer Valley; Mammoth; Heavenly; Palisades Tahoe; Steamboat; Telluride; Big Sky; Killington; Stowe; Sun Valley; Winter Park; Copper Mountain; Crested Butte; Northstar; Kirkwood; Taos Ski Valley; Snowbasin; Brighton; Solitude Mountain Resort; Arapahoe Basin; Eldora Mountain; Sugarbush Resort; Sunday River; Sugarloaf; Loon Mountain; Stratton Mountain Resort; Mt. Bachelor; Crystal Mountain Resort; Schweitzer; Alyeska Resort; Grand Targhee; Big Bear Mountain Resort; Sierra-at-Tahoe; June Mountain; Snow Valley; Brian Head; Arizona Snowbowl; Snowshoe Mountain; Camelback Resort; Powderhorn; Bromley Mountain; Summit at Snoqualmie; Cannon Mountain; Lutsen Mountains; The Highlands; Attitash Mountain Resort; White Pass; Boyne Mountain; Discovery Ski Area; Wenatchee Mission Ridge; Pico Mountain; Cranmore Mountain Resort; Lost Trail; Brundage Mountain') },
  { id: 'canada', he: 'קנדה', en: 'Canada', resorts: split(
    'Whistler Blackcomb; Banff; Le Massif de Charlevoix; Panorama; Red Mountain; Sun Peaks; Jasper; Revelstoke; Cypress Mountain; Mont Tremblant; Fernie; Blue Mountain; Lake Louise; Kicking Horse') },
  { id: 'japan', he: 'יפן', en: 'Japan', resorts: split(
    'Niseko; Tangram; Hakuba; Madarao; Shiga Kogen; Arai Mountain; Kiroro; Yuzawa Kogen; Mitsumata') },
  { id: 'new-zealand', he: 'ניו זילנד', en: 'New Zealand', resorts: split('Cardrona') },
]

// Hebrew names for the resorts Israelis actually search by name; the rest are
// shown (and searched) in their Latin spelling.
export const RESORT_HE = {
  'Tignes': 'טין', 'Val Thorens': 'ואל טורנס', 'Les Arcs': 'לז ארק', "Alpe d'Huez": 'אלפ ד׳הואז',
  'Avoriaz': 'אבוריאז', 'Méribel': 'מריבל', 'Morzine': 'מורזין', 'Les Menuires': 'לה מנואר',
  'Les Deux Alpes': 'לה דז אלפ', 'Chamonix': 'שאמוני', 'Flaine': 'פלן', "Val d'Isère": 'ואל ד׳איזר',
  'Megève': 'מז׳ב', 'La Plagne': 'לה פלאן', 'Courchevel': 'קורשבל', 'Serre Chevalier': 'סר שבלייה',
  'Risoul': 'ריזול', 'Vars': 'ואר',
  'Obergurgl-Hochgurgl': 'אוברגורגל', 'Seefeld': 'זיפלד', 'Saalbach': 'זאלבאך', 'Kaprun': 'קפרון',
  'Zell am See': 'צל אם זה', 'Mayrhofen': 'מאיירהופן', 'Bad Gastein': 'באד גסטיין',
  'St. Anton': 'סנט אנטון', 'Ischgl': 'אישגל', 'Kitzbühel': 'קיצביהל', 'Sölden': 'זלדן',
  'Lech Zürs': 'לך', 'Schladming': 'שלדמינג', 'Söll': 'זל',
  'Sestriere': 'ססטרייר', "Sauze D'Oulx": 'סאוזה ד׳אולקס', 'Val Gardena': 'ואל גרדנה',
  'Livigno': 'ליביניו', 'Breuil-Cervinia': 'צ׳רביניה', 'Courmayeur': 'קורמאייר',
  'Madonna di Campiglio': 'מדונה די קמפיליו', "Cortina d'Ampezzo": 'קורטינה ד׳אמפצו',
  'Passo Tonale': 'פאסו טונאלה', 'Canazei': 'קנאזיי', 'Bormio': 'בורמיו', 'Val di Fiemme': 'ואל די פיימה',
  'Zermatt': 'צרמט', 'Verbier': 'ורבייה', 'Grindelwald': 'גרינדלוואלד', 'St. Moritz': 'סנט מוריץ',
  'Davos': 'דאבוס', 'Crans-Montana': 'קראן מונטנה', 'Engelberg': 'אנגלברג', 'Laax': 'לאקס',
  'Pas de la Casa': 'פאס דה לה קאסה', 'Arinsal': 'ארינסל', 'Soldeu': 'סולדאו', 'El Tarter': 'אל טרטר',
  'Bansko': 'בנסקו', 'Borovets': 'בורובץ', 'Pamporovo': 'פמפורובו',
  'Gudauri': 'גודאורי', 'Garmisch-Partenkirchen': 'גרמיש פרטנקירכן',
  'Sierra Nevada': 'סיירה נבדה', 'Baqueira-Beret': 'בקיירה ברט', 'Zakopane': 'זקופנה',
  'Jasna Nizke Tatry': 'יאסנה', 'Kranjska Gora': 'קרניסקה גורה', 'Jahorina': 'יהורינה',
  'Whistler Blackcomb': 'ויסלר', 'Banff': 'באנף', 'Aspen Snowmass': 'אספן', 'Vail': 'וייל',
  'Park City': 'פארק סיטי', 'Breckenridge': 'ברקנרידג׳', 'Niseko': 'ניסקו', 'Hakuba': 'האקובה',
  'Levi': 'לוי', 'Trysil': 'טריסיל',
}

/** "ואל טורנס (Val Thorens)" in Hebrew, the Latin name in English. */
export function resortLabel(name, lang = 'he') {
  const he = RESORT_HE[name]
  return lang === 'he' && he ? `${he} (${name})` : name
}

export const SKI_RESORT_COUNT = SKI_COUNTRIES.reduce((n, c) => n + c.resorts.length, 0)
