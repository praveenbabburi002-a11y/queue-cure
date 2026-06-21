function showToast(message){

let toast =
document.createElement("div");

toast.className =
"toast show position-fixed top-0 end-0 m-3";

toast.innerHTML = `
<div class="toast-header">
<strong class="me-auto">
Queue Cure
</strong>
</div>
<div class="toast-body">
${message}
</div>
`;

document.body.appendChild(toast);

setTimeout(()=>{
toast.remove();
},3000);

}