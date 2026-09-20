let token=sessionStorage.getItem('sanitasmart-token'), user=null;
const api=async(path,options={})=>{const response=await fetch(`/api${path}`,{headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},...options});const data=response.status===204?{}:await response.json();if(!response.ok)throw new Error(data.error||'Operazione non riuscita');return data};
const toast=m=>{const e=document.querySelector('#toast');e.textContent=m;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),2800)};
const esc=v=>String(v).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const formData=f=>Object.fromEntries(new FormData(f).entries());
async function refresh(){const[d,p,a,r]=await Promise.all([api('/dashboard'),api('/patients'),api('/appointments'),api('/reports')]);document.querySelector('#metrics').innerHTML=[[d.patients,'Pazienti registrati'],[d.appointments,'Visite confermate'],[d.reports,'Referti disponibili'],[d.today,'Data odierna']].map(([n,l])=>`<div class="metric"><b>${esc(n)}</b><span>${esc(l)}</span></div>`).join('');document.querySelector('#patient-select').innerHTML=p.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('');document.querySelector('#appointment-count').textContent=`${a.length} registrate`;document.querySelector('#appointments').innerHTML=`<table><thead><tr><th>Paziente</th><th>Visita</th><th>Quando</th><th>Stato</th><th></th></tr></thead><tbody>${a.map(x=>`<tr><td>${esc(x.patientName)}</td><td>${esc(x.specialty)}<br><small>${esc(x.doctor)}</small></td><td>${esc(x.date)} ${esc(x.time)}</td><td class="status">${esc(x.status)}</td><td>${x.status==='Confermata'&&['admin','segreteria'].includes(user.role)?`<button class="cancel" data-id="${x.id}">Annulla</button>`:''}</td></tr>`).join('')}</tbody></table>`;document.querySelector('#reports').innerHTML=r.map(x=>`<div class="report"><b>${esc(x.type)} - ${esc(x.patientName)}</b><span>${esc(x.date)} · ${esc(x.outcome)}</span></div>`).join('');document.querySelectorAll('.cancel').forEach(b=>b.onclick=async()=>{try{await api(`/appointments/${b.dataset.id}/cancel`,{method:'PATCH'});toast('Appuntamento annullato');refresh()}catch(e){toast(e.message)}})}
async function slots(){const doctor=document.querySelector('#doctor').value.trim(),date=document.querySelector('#visit-date').value,select=document.querySelector('#visit-time'),note=document.querySelector('#availability');if(!doctor||!date)return;try{const data=await api(`/availability?doctor=${encodeURIComponent(doctor)}&date=${date}`);select.innerHTML=`<option value="">Scegli un orario</option>${data.available.map(x=>`<option value="${x}">${x}</option>`).join('')}`;note.textContent=data.booked.length?`Gia occupati: ${data.booked.join(', ')}`:'Tutti gli orari sono disponibili'}catch(e){note.textContent=e.message}}
function showApp(){document.querySelector('#login-view').classList.add('hidden');document.querySelector('#app-view').classList.remove('hidden');document.querySelector('#account').classList.remove('hidden');document.querySelector('#user-name').textContent=`${user.name} · ${user.role}`;document.querySelector('#role-description').textContent=user.role==='medico'?'Puoi consultare i dati e pubblicare referti tramite API.':'Puoi registrare pazienti, controllare gli orari disponibili e prenotare visite.';document.querySelectorAll('.staff-only').forEach(x=>x.classList.toggle('hidden',!['admin','segreteria'].includes(user.role)));refresh().catch(e=>toast(e.message))}
document.querySelector('#login-form').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget;try{const data=await api('/login',{method:'POST',body:JSON.stringify(formData(f))});token=data.token;user=data.user;sessionStorage.setItem('sanitasmart-token',token);showApp()}catch(err){toast(err.message)}};
document.querySelector('#logout').onclick=async()=>{
    const button=document.querySelector('#logout');
    button.disabled=true;
    try{
        await api('/logout',{method:'POST',body:JSON.stringify({})});
        sessionStorage.removeItem('sanitasmart-token');
        token=null;user=null;
        location.reload();
    }catch(err){
        toast(`Impossibile uscire: ${err.message}`);
    }finally{
        button.disabled=false;
    }
};
document.querySelector('#appointment-form').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget;try{await api('/appointments',{method:'POST',body:JSON.stringify(formData(f))});f.reset();document.querySelector('#visit-time').innerHTML='<option value="">Scegli prima medico e data</option>';toast('Visita prenotata');refresh()}catch(err){toast(err.message)}};
document.querySelector('#patient-form').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget;try{await api('/patients',{method:'POST',body:JSON.stringify(formData(f))});f.reset();toast('Paziente registrato');refresh()}catch(err){toast(err.message)}};
document.querySelector('#doctor').onchange=slots;document.querySelector('#visit-date').onchange=slots;
if(token)api('/me').then(x=>{user=x;showApp()}).catch(()=>sessionStorage.removeItem('sanitasmart-token'));
