"""Small ES3 adapter for the Shop browser native objects; no replacement layout."""

JS = b'''var nativeShop=null,nativeSound=null,nativeKeyboard=null,connectingText=null;
function soundEffect(n){try{if(nativeSound)nativeSound.playSE(n);}catch(e){}}
function leaveShop(){try{if(nativeShop){nativeShop.returnToMenu();return false;}}catch(e){}return true;}
function typeSearch(){try{if(nativeKeyboard)nativeKeyboard.call(3,1,false);}catch(e){}}
function previewHover(id,url){var image=document.getElementById(id);if(image)image.src=url;}
function initShop(){var bridge=0,music=0;
try{nativeShop=new wiiShop();connectingText=nativeShop.connecting;nativeShop.setWallpaper(0);nativeShop.enableHRP();nativeShop.endWaiting();bridge=1;}catch(e){}
try{nativeSound=new wiiSound();nativeSound.playBGM();music=1;}catch(e){}
try{nativeKeyboard=new wiiKeyboard();}catch(e){}
var w=window.innerWidth||document.documentElement.clientWidth||document.body.clientWidth;
var h=window.innerHeight||document.documentElement.clientHeight||document.body.clientHeight;
var image=new Image();window.readyImage=image;image.src='/ready?w='+w+'&h='+h+'&bridge='+bridge+'&music='+music;
}
'''
