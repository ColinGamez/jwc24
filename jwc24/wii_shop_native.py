"""Small ES3 adapter for the Shop browser native objects; no replacement layout."""

JS = b'''var nativeShop=null,nativeSound=null,nativeKeyboard=null,connectingText=null;
function soundEffect(n){try{if(nativeSound)nativeSound.playSE(n);}catch(e){}}
function leaveShop(){try{if(nativeShop){nativeShop.returnToMenu();return false;}}catch(e){}return true;}
function typeSearch(input){input.blur();try{if(nativeKeyboard)nativeKeyboard.call(cKT_PredictNoLF,5,false);}catch(e){}}
function submitCatalogSearch(input){input.blur();var value=input.value;input.value='';
if(value){var category=input.getAttribute('data-shop-category');
window.location.href='/catalog?category='+encodeURIComponent(category)+'&q='+encodeURIComponent(value);}}
function applyShopStrings(){var nodes=document.getElementsByTagName('span');
for(var i=0;i<nodes.length;i++){var key=nodes[i].getAttribute('data-shop-string');
if(key=='title'||key=='menuBtn'){var text=nativeShop[key];
while(nodes[i].firstChild)nodes[i].removeChild(nodes[i].firstChild);
nodes[i].appendChild(document.createTextNode(text));}}
document.title=nativeShop.title;}
function initShop(){var bridge=0,music=0,keyboardReady=0;
try{nativeShop=shop;connectingText=nativeShop.connecting;nativeShop.setWallpaper(cWP_Dots);nativeShop.enableHRP();nativeShop.endWaiting();applyShopStrings();bridge=1;}catch(e){}
try{nativeSound=snd;nativeSound.playBGM();music=1;}catch(e){}
try{nativeKeyboard=kbd;keyboardReady=1;}catch(e){}
var w=window.innerWidth||document.documentElement.clientWidth||document.body.clientWidth;
var h=window.innerHeight||document.documentElement.clientHeight||document.body.clientHeight;
var image=new Image();window.readyImage=image;image.src='/ready?w='+w+'&h='+h+'&bridge='+bridge+'&music='+music+'&keyboard='+keyboardReady;
}
'''
