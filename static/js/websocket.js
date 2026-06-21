const socket = new WebSocket(
"ws://" +
window.location.host +
"/ws/queue/"
);

socket.onmessage = function(event){

const data =
JSON.parse(event.data);

if(
typeof showToast !== 'undefined'
){
showToast(
data.message
);
}

const token =
document.getElementById(
"current-token"
);

if(token){
token.innerText =
data.current_token;
}

setTimeout(()=>{
location.reload();
},1000);

};