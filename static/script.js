
const musicFile=document.getElementById("musicFile");
const musicPlayer=document.getElementById("musicPlayer");
const musicName=document.getElementById("musicName");
let musicObjectUrl=null;
musicFile.addEventListener("change",()=>{const file=musicFile.files[0];if(musicObjectUrl){URL.revokeObjectURL(musicObjectUrl);musicObjectUrl=null}if(!file){musicPlayer.removeAttribute("src");musicPlayer.load();musicName.textContent="Belum ada musik";return}if(!file.type.startsWith("audio/")){musicFile.value="";musicPlayer.removeAttribute("src");musicPlayer.load();musicName.textContent="File bukan audio";setStatus("Pilih file musik/audio yang valid.");return}musicObjectUrl=URL.createObjectURL(file);musicPlayer.src=musicObjectUrl;musicName.textContent=file.name;setStatus("Musik siap diputar. Tekan ▶ pada pemutar.")});
window.addEventListener("beforeunload",()=>{if(musicObjectUrl)URL.revokeObjectURL(musicObjectUrl)});

const form=document.getElementById("deployForm"),zipInput=document.getElementById("siteZip"),statusText=document.getElementById("statusText"),result=document.getElementById("result"),deployBtn=document.getElementById("deployBtn"),checkBtn=document.getElementById("checkBtn");
function setStatus(t){statusText.textContent=t}
async function refreshStatus(){try{const r=await fetch("/status");const d=await r.json();setStatus(d.message);if(d.url){result.classList.remove("hidden");result.innerHTML=`🌐 Website: <a href="${d.url}" target="_blank" rel="noopener">${d.url}</a>`}deployBtn.disabled=!!d.running}catch(e){setStatus("Server tidak dapat dihubungi.")}}
checkBtn.addEventListener("click",async()=>{const file=zipInput.files[0];if(!file){alert("Pilih ZIP terlebih dahulu.");return}const fd=new FormData();fd.append("site_zip",file);setStatus("Memeriksa ZIP...");try{const r=await fetch("/preview",{method:"POST",body:fd});const d=await r.json();setStatus(d.message);if(d.ok&&d.files){result.classList.remove("hidden");result.innerHTML="<b>File yang ditemukan:</b><br>"+d.files.map(escapeHtml).map(x=>`<code>${x}</code>`).join("<br>")}}catch(e){setStatus("Gagal memeriksa ZIP.")}});
form.addEventListener("submit",async e=>{e.preventDefault();const file=zipInput.files[0];if(!file){alert("Pilih ZIP website.");return}const fd=new FormData(form);deployBtn.disabled=true;setStatus("Mengirim deployment...");result.classList.add("hidden");try{const r=await fetch("/deploy",{method:"POST",body:fd});const d=await r.json();setStatus(d.message);if(!d.ok)deployBtn.disabled=false}catch(e){setStatus("Gagal menghubungi server.");deployBtn.disabled=false}});
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}
setInterval(refreshStatus,1500);refreshStatus();
