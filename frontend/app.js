const $ = (id) => document.getElementById(id);

const samplePayload = (executionId) => ({
  execution_id: executionId,
  correlation_id: executionId + ":corr",
  observations: [
    {item_id:"P1.sleep_quality",value:8,observation_id:executionId+":sleep"},
    {item_id:"P1.recovery_index",value:8,observation_id:executionId+":recovery"},
    {item_id:"P1.physical_activity",value:7,observation_id:executionId+":activity"},
    {item_id:"P1.metabolic_stability",value:8,observation_id:executionId+":metabolic"},
    {item_id:"P1.subjective_stress",value:2,observation_id:executionId+":stress"},
    {item_id:"P1.subjective_energy",value:8,observation_id:executionId+":energy"}
  ],
  study: {
    study_id:executionId+":study", study_code:executionId, title:"Science Lab Study",
    research_question:"Does the scenario change the primary outcome?", hypothesis_ids:["H1"],
    design_type:"SYNTHETIC", protocol_version:"1.2", preregistration_ref:"synthetic",
    population_definition:{synthetic:true}, inclusion_criteria:{}, exclusion_criteria:{},
    primary_outcomes:["value"], secondary_outcomes:[]
  },
  protocol: {
    protocol_id:executionId+":protocol", version:"1.2",
    design:{type:"SYNTHETIC"}, measurement_schedule:{frequency:"once"},
    analysis_plan:{primary:"mean"}
  },
  experiment: {
    experiment_id:executionId+":experiment", experiment_code:"E1",
    intervention_spec:{name:"scenario"}, comparator_spec:null,
    randomization_spec:null, blinding_spec:null, duration_days:1,
    measurement_schedule:{frequency:"once"}, analysis_plan:{primary:"mean"},
    seed:42, software_version:"2.3"
  },
  arm: {
    arm_id:executionId+":arm", arm_code:"I", arm_type:"INTERVENTION",
    intervention:{name:"scenario"}, target_level:"B", sample_target:1
  },
  participant: {
    participant_id:executionId+":participant", external_participant_code:"P1",
    eligibility_status:"ELIGIBLE", consent_status:"CONSENTED",
    enrollment_date:"2026-09-27", withdrawal_date:null,
    demographic_snapshot:{synthetic:true}, baseline_snapshot_id:null
  },
  assignment: {
    assignment_id:executionId+":assignment", participant_id:executionId+":participant",
    arm_id:executionId+":arm", assignment_method:"SYNTHETIC",
    randomization_seed:42, status:"ACTIVE"
  },
  trial: {
    trial_id:executionId+":trial", participant_id:executionId+":participant",
    arm_id:executionId+":arm", trial_number:1,
    trial_time:"2026-09-27T12:00:00+00:00", task_id:"science-lab-task",
    condition:{scenario:"baseline"}, stimulus:null, response:{rt:500},
    outcome:{value:7}, duration_ms:500, validity_status:"VALID", raw_payload:{value:7}
  },
  requested_trait:null, blockers:{}, recovery_indices:[8,8,8]
});

const api = async (url, options={}) => {
  const headers = {"Content-Type":"application/json", ...(options.headers || {})};
  const key = localStorage.getItem("CTE_API_KEY") || "";
  if (key) headers["X-CTE-API-Key"] = key;
  const res = await fetch(url, {...options, headers});
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
};

const out = (value) => {
  $("output").textContent = typeof value === "string" ? value : JSON.stringify(value,null,2);
};


async function loadOverview(){
  try{
    const id=encodeURIComponent($("matrixId").value);
    const [overview,stats]=await Promise.all([
      api("/science-lab/matrices/"+id),
      api("/science-lab/matrices/"+id+"/statistics")
    ]);
    const metrics=[
      ["Scenarios",stats.scenario_count],
      ["Runs",stats.run_count],
      ["Completed",stats.completed_runs],
      ["Blocked",stats.blocked_runs],
      ["Primary estimate",stats.descriptive_estimate_mean ?? "—"]
    ];
    $("metrics").innerHTML=metrics.map(([label,value]) =>
      "<div><span>"+label+"</span><strong>"+value+"</strong></div>"
    ).join("");
    const rows=overview.scenario_runs || [];
    const defs=Object.fromEntries((overview.scenarios || []).map(x=>[x.scenario_id,x]));
    $("scenarioTable").querySelector("tbody").innerHTML = rows.length
      ? rows.map(row => {
          const def=defs[row.scenario_id] || {};
          return "<tr><td>"+row.scenario_id+"</td><td><code>"+escapeHtml(JSON.stringify(def.conditions || {}))+
                 "</code></td><td>"+row.status+"</td><td>"+(row.estimate_by_outcome?.value ?? "—")+"</td></tr>";
        }).join("")
      : "<tr><td colspan="4">No scenario runs yet.</td></tr>";
  }catch(e){
    $("output").textContent="ERROR: "+e.message;
  }
}

async function loadClaims(){
  try{
    const id=encodeURIComponent($("matrixId").value);
    $("claims").textContent=JSON.stringify(await api("/science-lab/matrices/"+id+"/claims"),null,2);
  }catch(e){
    $("claims").textContent="ERROR: "+e.message;
  }
}

function escapeHtml(value){
  return String(value).replace(/[&<>"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",""":"&quot;"}[char]));
}

async function boot(){
  const apiKeyInput = $("apiKey");
  apiKeyInput.value = localStorage.getItem("CTE_API_KEY") || "";
  apiKeyInput.addEventListener("change", () => localStorage.setItem("CTE_API_KEY", apiKeyInput.value));
  try{
    await api("/science-lab/matrices/nonexistent");
  }catch(e){
    $("apiStatus").textContent = "API: online";
    $("apiStatus").dataset.online = "true";
  }
  $("runPayload").value = JSON.stringify(samplePayload($("executionId").value),null,2);
  await loadOverview();
}

$("createMatrix").onclick = async () => {
  try{
    const data=await api("/science-lab/matrices",{method:"POST",body:JSON.stringify({
      matrix_id:$("matrixId").value,study_id:$("studyId").value,name:$("matrixName").value,
      primary_outcome:$("primaryOutcome").value,design:{type:"scenario_matrix"}
    })});
    out(data);
  }catch(e){out("ERROR: "+e.message)}
};

$("generateScenarios").onclick = async () => {
  try{
    const data=await api("/science-lab/matrices/"+encodeURIComponent($("matrixId").value)+"/generate-scenarios",{
      method:"POST",
      body:JSON.stringify({
        factors:JSON.parse($("factors").value),
        max_scenarios:128,
        name_prefix:"Factorial"
      })
    });
    out(data);
  }catch(e){out("ERROR: "+e.message)}
};

$("createScenario").onclick = async () => {
  try{
    const data=await api("/science-lab/matrices/"+encodeURIComponent($("matrixId").value)+"/scenarios",{method:"POST",body:JSON.stringify({
      scenario_id:$("scenarioId").value,name:$("scenarioName").value,
      description:$("scenarioDescription").value,conditions:JSON.parse($("conditions").value),
      expected_outcomes:[$("primaryOutcome").value],independent:true
    })});
    out(data);
    await loadOverview();
  }catch(e){out("ERROR: "+e.message)}
};

$("runScenario").onclick = async () => {
  try{
    const data=await api(
      "/science-lab/matrices/"+encodeURIComponent($("matrixId").value)+"/scenarios/"+encodeURIComponent($("scenarioId").value)+"/run",
      {method:"POST",body:JSON.stringify({payload:JSON.parse($("runPayload").value)})}
    );
    out(data);
    await loadOverview();
  }catch(e){out("ERROR: "+e.message)}
};

$("loadStats").onclick = async () => {
  try{
    const data=await api("/science-lab/matrices/"+encodeURIComponent($("matrixId").value)+"/statistics");
    $("stats").textContent=JSON.stringify(data,null,2);
  }catch(e){$("stats").textContent="ERROR: "+e.message}
};

$("loadReport").onclick = async () => {
  try{
    const data=await api("/science-lab/matrices/"+encodeURIComponent($("matrixId").value)+"/report");
    $("report").textContent=JSON.stringify(data,null,2);
  }catch(e){$("report").textContent="ERROR: "+e.message}
};

$("executionId").addEventListener("change",()=>{
  $("runPayload").value=JSON.stringify(samplePayload($("executionId").value),null,2);
});

boot();

$("loadOverview").onclick = loadOverview;
$("loadClaims").onclick = loadClaims;
