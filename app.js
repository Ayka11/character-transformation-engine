const $=id=>document.getElementById(id);
const STORE="cpe-static-science-lab-v1";
const state={matrix:null,scenarios:[],runs:[],claims:[],provenance:[],replication:null};

function hash(text){let h=2166136261;for(let i=0;i<text.length;i++){h^=text.charCodeAt(i);h=Math.imul(h,16777619)}return ("00000000"+(h>>>0).toString(16)).slice(-8)}
function now(){return new Date().toISOString()}
function save(){localStorage.setItem(STORE,JSON.stringify(state))}
function load(){try{const x=JSON.parse(localStorage.getItem(STORE)||"null");if(x)Object.assign(state,x)}catch{}}
function out(v){$("output").textContent=typeof v==="string"?v:JSON.stringify(v,null,2)}
function pretty(id,v){$(id).textContent=JSON.stringify(v,null,2)}
function escapeHtml(v){return String(v).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}

function deterministicValue(scenario,rep=0){
 const c=scenario.conditions||{};let effect=0;
 if(c.dose!==undefined)effect+=(Number(c.dose)||0)*.8;
 if(c.tempo==="fast")effect+=.35;if(c.tempo==="slow")effect-=.15;
 if(c.level!==undefined)effect+=(Number(c.level)||0)*.1;
 const jitter=((parseInt(hash(scenario.scenario_id+":"+rep),16)%101)/100-.5)*.4;
 return Math.max(0,Math.min(10,7+effect+jitter));
}
function record(type,payload){
 const entry={event_id:hash(type+JSON.stringify(payload)+now()),type,timestamp:now(),algorithm_version:"CPE-STATIC-1.0",
 input_hash:hash(JSON.stringify(payload)),output_hash:hash(JSON.stringify(payload)+type)};
 state.provenance.push(entry);return entry;
}
function createMatrix(){
 state.matrix={matrix_id:$("matrixId").value.trim()||"demo-matrix",study_id:$("studyId").value.trim()||"demo-study",
 name:$("matrixName").value.trim()||"CPE Static Science Lab",primary_outcome:$("primaryOutcome").value.trim()||"value",
 design:{type:"scenario_matrix",execution_mode:"STATIC_BROWSER"},created_at:now(),software_version:"CPE-STATIC-1.0"};
 state.scenarios=[];state.runs=[];state.claims=[];state.replication=null;state.provenance=[];
 record("MATRIX_CREATED",state.matrix);save();refresh();out({status:"created",matrix:state.matrix});
}
function createScenario(){
 if(!state.matrix)createMatrix();let conditions={};
 try{conditions=JSON.parse($("conditions").value||"{}")}catch(e){out("Invalid conditions JSON: "+e.message);return}
 const scenario={scenario_id:$("scenarioId").value.trim()||"scenario-"+(state.scenarios.length+1),name:$("scenarioName").value.trim()||"Scenario",
 description:$("scenarioDescription").value.trim(),conditions,expected_outcomes:[state.matrix.primary_outcome],independent:true,created_at:now()};
 const idx=state.scenarios.findIndex(x=>x.scenario_id===scenario.scenario_id);if(idx>=0)state.scenarios[idx]=scenario;else state.scenarios.push(scenario);
 record("SCENARIO_CREATED",scenario);save();refresh();out(scenario);
}
function generateScenarios(){
 if(!state.matrix)createMatrix();let factors;try{factors=JSON.parse($("factors").value||"{}")}catch(e){out("Invalid factors JSON: "+e.message);return}
 const keys=Object.keys(factors);if(!keys.length){out("No factorial factors supplied.");return}let combos=[{}];
 for(const key of keys){const vals=Array.isArray(factors[key])?factors[key]:[factors[key]];combos=combos.flatMap(c=>vals.map(v=>({...c,[key]:v})))} 
 combos.slice(0,128).forEach((conditions,i)=>{const id="factorial-"+String(i+1).padStart(3,"0");
 const s={scenario_id:id,name:"Factorial "+(i+1),description:"Generated factorial scenario",conditions,expected_outcomes:[state.matrix.primary_outcome],independent:true,created_at:now()};
 const idx=state.scenarios.findIndex(x=>x.scenario_id===id);if(idx>=0)state.scenarios[idx]=s;else state.scenarios.push(s)});
 record("FACTORIAL_GENERATED",{factors,count:Math.min(combos.length,128)});save();refresh();out({generated:Math.min(combos.length,128),factors});
}
function runScenario(){
 if(!state.matrix)createMatrix();let payload={};try{payload=JSON.parse($("runPayload").value||"{}")}catch(e){out("Invalid run payload JSON: "+e.message);return}
 const scenarioId=$("scenarioId").value.trim()||"baseline";let scenario=state.scenarios.find(x=>x.scenario_id===scenarioId);
 if(!scenario){scenario={scenario_id:scenarioId,name:scenarioId,description:"Implicit static scenario",conditions:{},expected_outcomes:[state.matrix.primary_outcome],independent:true,created_at:now()};state.scenarios.push(scenario)}
 const n=Math.max(1,Math.min(100,Number($("replications").value)||1)),executionId=$("executionId").value.trim()||("run-"+Date.now()),values=[];
 for(let i=0;i<n;i++)values.push(Number(deterministicValue(scenario,i).toFixed(4)));
 const mean=values.reduce((a,b)=>a+b,0)/values.length,variance=values.reduce((a,b)=>a+(b-mean)**2,0)/values.length;
 const run={execution_id:executionId,correlation_id:executionId+":corr",scenario_id:scenarioId,status:"COMPLETED",outcome:state.matrix.primary_outcome,
 values,estimate:Number(mean.toFixed(4)),variance:Number(variance.toFixed(4)),payload_hash:hash(JSON.stringify(payload)),algorithm_version:"CPE-STATIC-1.0",synthetic:true,created_at:now()};
 state.runs=state.runs.filter(x=>x.execution_id!==executionId);state.runs.push(run);record("SCENARIO_RUN",run);save();refresh();out(run);
}
function stats(){
 const values=state.runs.flatMap(r=>r.values||[]),mean=values.length?values.reduce((a,b)=>a+b,0)/values.length:null;
 const sd=values.length?Math.sqrt(values.reduce((a,b)=>a+(b-(mean||0))**2,0)/values.length):null;
 return {matrix_id:state.matrix?.matrix_id||null,scenario_count:state.scenarios.length,run_count:state.runs.length,
 completed_runs:state.runs.filter(r=>r.status==="COMPLETED").length,blocked_runs:state.runs.filter(r=>r.status==="BLOCKED").length,
 observation_count:values.length,descriptive_estimate_mean:mean===null?null:Number(mean.toFixed(4)),descriptive_sd:sd===null?null:Number(sd.toFixed(4)),synthetic:true};
}
function refresh(){
 const s=stats();$("metrics").innerHTML=[["Scenarios",s.scenario_count],["Runs",s.run_count],["Completed",s.completed_runs],["Blocked",s.blocked_runs],["Primary estimate",s.descriptive_estimate_mean??"—"]].map(([a,b])=>"<div><span>"+a+"</span><strong>"+b+"</strong></div>").join("");
 const body=$("scenarioTable").querySelector("tbody");
 body.innerHTML=state.scenarios.length?state.scenarios.map(sc=>{const runs=state.runs.filter(r=>r.scenario_id===sc.scenario_id);
 const estimate=runs.length?(runs.reduce((a,r)=>a+r.estimate,0)/runs.length).toFixed(4):"—";
 return "<tr><td>"+escapeHtml(sc.scenario_id)+"</td><td><code>"+escapeHtml(JSON.stringify(sc.conditions))+"</code></td><td>"+(runs.length?"COMPLETED":"DEFINED")+"</td><td>"+estimate+"</td></tr>"}).join(""):"<tr><td colspan=\"4\">No scenarios yet.</td></tr>";
}
function runReplication(){
 const groups={};state.runs.forEach(r=>(groups[r.scenario_id]??=[]).push(r.estimate));
 const rows=Object.entries(groups).map(([id,v])=>{const m=v.reduce((a,b)=>a+b,0)/v.length,spread=Math.sqrt(v.reduce((a,b)=>a+(b-m)**2,0)/v.length);
 return {scenario_id:id,runs:v.length,mean:Number(m.toFixed(4)),sd:Number(spread.toFixed(4)),replication_status:v.length>1?"REPLICATED":"SINGLE_RUN"}});
 state.replication={type:"REPLICATION_ANALYSIS",created_at:now(),rows,generalization:{target_population:"synthetic browser scenarios",target_context:"static Space",transport_error:"NOT_ESTIMATED",status:"DESCRIPTIVE_ONLY"}};
 record("REPLICATION_ANALYSIS",state.replication);save();pretty("replication",state.replication);out(state.replication);
}
function validateClaim(){
 const s=stats(),hasRuns=s.completed_runs>0,replicated=state.replication?.rows?.some(x=>x.replication_status==="REPLICATED")||false;
 const claim={claim_id:"claim-"+(state.matrix?.matrix_id||"none"),statement:hasRuns?"The configured synthetic scenario produced a measurable primary-outcome estimate in the browser runtime.":"No evidence-supported claim can be formed because no completed runs exist.",
 status:hasRuns&&replicated?"MODEL_REPLICATION_SUPPORTED":"IMPLEMENTATION_BASELINE",evidence_ids:state.runs.map(r=>r.execution_id),replication_present:replicated,empirical_validation:false,
 notes:"Browser execution demonstrates implementation behavior; it does not establish empirical validity."};
 state.claims=[claim];record("CLAIM_VALIDATION",claim);save();pretty("claims",claim);out(claim);
}
function report(){
 const report={report_id:"report-"+hash(JSON.stringify(state)+now()),generated_at:now(),software_version:"CPE-STATIC-1.0",scientific_status:"IMPLEMENTATION_BASELINE",
 matrix:state.matrix,statistics:stats(),scenarios:state.scenarios,runs:state.runs,replication:state.replication,claims:state.claims,provenance:state.provenance,
 limitations:["Synthetic browser execution only","No empirical validation","No clinical inference","Generalization transport error not estimated"]};
 pretty("report",report);record("REPORT_GENERATED",report);save();return report;
}
function exportReport(){
 const data=report(),blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"}),a=document.createElement("a");
 a.href=URL.createObjectURL(blob);a.download=(state.matrix?.matrix_id||"cpe")+"-static-report.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
function clearData(){localStorage.removeItem(STORE);location.reload()}
function boot(){
 load();refresh();
 $("runPayload").value=JSON.stringify({execution_id:"demo-run-001",observations:[{item_id:"P1.sleep_quality",value:8},{item_id:"P1.recovery_index",value:8},{item_id:"P1.subjective_stress",value:2},{item_id:"P1.subjective_energy",value:8}],
 study:{design_type:"SYNTHETIC"},protocol:{version:"1.2"},experiment:{seed:42},scientific_status:"implementation_baseline"},null,2);
 if(state.matrix)out({status:"restored",matrix_id:state.matrix.matrix_id,stats:stats()});
}
$("createMatrix").onclick=createMatrix;$("createScenario").onclick=createScenario;$("generateScenarios").onclick=generateScenarios;$("runScenario").onclick=runScenario;
$("loadStats").onclick=()=>pretty("stats",stats());$("runReplication").onclick=runReplication;$("loadClaims").onclick=validateClaim;$("loadReport").onclick=report;$("exportReport").onclick=exportReport;$("clearData").onclick=clearData;
$("executionId").onchange=()=>{const x=JSON.parse($("runPayload").value||"{}");x.execution_id=$("executionId").value;$("runPayload").value=JSON.stringify(x,null,2)};boot();