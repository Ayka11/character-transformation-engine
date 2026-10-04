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
        : "<tr><td colspan=\"4\">No scenario runs yet.</td></tr>";
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
  return String(value).replace(/[&<>"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[char]));
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
}

$("createMatrix").onclick = async () => {
  try{
    const data=await api("/science-lab/matrices",{method:"POST",body:JSON.stringify({
      matrix_id:$("matrixId").value,study_id:$("studyId").value,name:$("matrixName").value,
      primary_outcome:$("primaryOutcome").value,design:{type:"scenario_matrix"}
    })});
    out(data);
    await loadOverview();
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
$("loadComparison").onclick = async () => {
  try{
    const id=encodeURIComponent($("matrixId").value);
    $("comparison").textContent=JSON.stringify(await api("/science-lab/matrices/"+id+"/comparison"),null,2);
  }catch(e){$("comparison").textContent="ERROR: "+e.message}
};


// Guided practical modules --------------------------------------------------
let masterMatrixItems = [];

function observationsFromSliders(executionId) {
  const fields = [
    ["P1.sleep_quality", "mSleep", "sleep"],
    ["P1.recovery_index", "mRecovery", "recovery"],
    ["P1.physical_activity", "mActivity", "activity"],
    ["P1.metabolic_stability", "mMetabolic", "metabolic"],
    ["P1.subjective_stress", "mStress", "stress"],
    ["P1.subjective_energy", "mEnergy", "energy"]
  ];
  return fields.map(([item_id, inputId, suffix]) => ({
    item_id,
    value: Number($(inputId).value),
    observation_id: executionId + ":" + suffix
  }));
}

function currentCharacterPayload() {
  const id = "character-lab-" + new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);
  return { observations: observationsFromSliders(id), source_id: id, source_version: "1.0" };
}

function showResult(elementId, title, value, note = "") {
  const root = $(elementId);
  root.replaceChildren();
  const heading = document.createElement("strong");
  heading.textContent = title;
  root.appendChild(heading);
  if (note) {
    const p = document.createElement("p");
    p.textContent = note;
    root.appendChild(p);
  }
  const pre = document.createElement("pre");
  pre.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  root.appendChild(pre);
}

function renderMasterMatrix() {
  const query = ($("matrixSearch").value || "").trim().toLowerCase();
  const domain = $("matrixDomain").value;
  const filtered = masterMatrixItems.filter(item => {
    const text = [item.id, item.domain, item.name, item.kind, item.notes, item.scale].join(" ").toLowerCase();
    return (!query || text.includes(query)) && (!domain || item.domain === domain);
  });
  $("matrixSummary").textContent = masterMatrixItems.length
    ? filtered.length + " of " + masterMatrixItems.length + " measures shown · catalogue v" + (window.cteMatrixVersion || "1.0")
    : "No catalogue loaded yet.";
  const list = $("matrixList");
  list.replaceChildren();
  if (!filtered.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No measures match this search. Try another word or choose All domains.";
    list.appendChild(empty);
    return;
  }
  filtered.forEach(item => {
    const row = document.createElement("article");
    row.className = "matrix-item";
    const title = document.createElement("div");
    title.className = "matrix-item-title";
    const name = document.createElement("strong");
    name.textContent = item.name;
    const domainTag = document.createElement("span");
    domainTag.className = "domain-tag";
    domainTag.textContent = item.domain;
    title.append(name, domainTag);
    const meta = document.createElement("p");
    meta.textContent = item.id + " · " + item.kind + " · scale " + item.scale + " · " + item.provenance_tag;
    const notes = document.createElement("p");
    notes.className = "muted";
    notes.textContent = item.notes || "Use as a defined measurement; interpret it alongside its domain and source.";
    row.append(title, meta, notes);
    list.appendChild(row);
  });
}

$("loadMasterMatrix").onclick = async () => {
  try {
    const data = await api("/matrix");
    masterMatrixItems = data.items || [];
    window.cteMatrixVersion = data.version;
    renderMasterMatrix();
    const counts = {};
    masterMatrixItems.forEach(item => { counts[item.domain] = (counts[item.domain] || 0) + 1; });
    $("matrixSummary").textContent = "Loaded " + masterMatrixItems.length + " measures · version " + data.version +
      " · " + Object.entries(counts).map(([key, count]) => key + ": " + count).join(" · ");
  } catch (e) {
    $("matrixSummary").textContent = "Could not load the catalogue: " + e.message;
  }
};
$("matrixSearch").addEventListener("input", renderMasterMatrix);
$("matrixDomain").addEventListener("change", renderMasterMatrix);

[
  ["mSleep", "vSleep"], ["mRecovery", "vRecovery"], ["mActivity", "vActivity"],
  ["mMetabolic", "vMetabolic"], ["mStress", "vStress"], ["mEnergy", "vEnergy"]
].forEach(([inputId, valueId]) => {
  $(inputId).addEventListener("input", () => { $(valueId).textContent = $(inputId).value; });
});

$("assessCharacter").onclick = async () => {
  try {
    const data = await api("/runtime/state-capacity", {
      method: "POST", body: JSON.stringify(currentCharacterPayload())
    });
    const capacity = data.capacity || {};
    const state = data.state || {};
    showResult("characterResult", "Your current-state snapshot",
      {state, capacity, adaptive_level: data.adaptive_level, missing_state_inputs: data.missing_state_inputs},
      "This is a snapshot of the values entered today, not a stable personality label. Reassess under comparable conditions to explore change.");
  } catch (e) {
    showResult("characterResult", "Assessment could not be completed", e.message,
      "Check that the API is online and that the deployment exposes /runtime/state-capacity.");
  }
};

$("buildSprint").onclick = async () => {
  try {
    const payload = {
      ...currentCharacterPayload(),
      requested_trait: $("targetTrait").value,
      supporting_bio_habit: $("bioHabit").value.trim(),
      daily_action: $("dailyAction").value.trim(),
      blockers: {}
    };
    const data = await api("/runtime/intervention", {method: "POST", body: JSON.stringify(payload)});
    showResult("characterResult", "Draft practice plan", data,
      "Treat this as a starting draft. Choose a small action you can safely repeat, record what actually happened, and adjust based on capacity—not willpower alone.");
  } catch (e) {
    showResult("characterResult", "Practice plan could not be created", e.message,
      "Check the selected target and confirm that the API exposes /runtime/intervention.");
  }
};

function parseCsv(input) {
  return input.split(",").map(value => value.trim()).filter(Boolean);
}
const exampleProfileA = {"P4.value_order":8,"P4.value_autonomy":6,"P5.discipline_consistency":7,"P5.adaptability":6};
const exampleProfileB = {"P4.value_order":5,"P4.value_autonomy":9,"P5.discipline_consistency":6,"P5.adaptability":8};
$("loadCompatExample").onclick = () => {
  $("profileA").value = JSON.stringify(exampleProfileA, null, 2);
  $("profileB").value = JSON.stringify(exampleProfileB, null, 2);
  $("rolesA").value = "Organizer, Strategist";
  $("rolesB").value = "Mediator, Strategist";
  $("compatContexts").value = "team project, decision making";
  $("compatSummary").textContent = "Demo profiles restored. Edit the values to match your scenario, then compare.";
  $("compatOutput").textContent = "{}";
};

$("runCompatibility").onclick = async () => {
  try {
    const payload = {
      profile_a: JSON.parse($("profileA").value),
      profile_b: JSON.parse($("profileB").value),
      roles_a: parseCsv($("rolesA").value),
      roles_b: parseCsv($("rolesB").value),
      contexts: parseCsv($("compatContexts").value)
    };
    const data = await api("/compatibility/v2/canonical", {method: "POST", body: JSON.stringify(payload)});
    const semantics = data.result_semantics || {};
    const coverage = data.coverage || {};
    $("compatSummary").textContent =
      "Status: " + (data.status || "UNKNOWN") + " · " +
      "Observed/descriptive rows: " + (semantics.descriptive_row_count ?? "—") + " · " +
      "Conditional heuristics: " + (semantics.heuristic_row_count ?? "—") + " · " +
      "Unknown rows: " + (semantics.unknown_row_count ?? "—") + " · " +
      "Coverage: " + (coverage.known_rows ?? 0) + "/" + (coverage.total_rows ?? 0) +
      ". " + (semantics.warning || "Review each finding and discuss context with the people involved.");
    $("compatOutput").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("compatSummary").textContent = "Comparison could not be completed: " + e.message;
    $("compatOutput").textContent = "Check that each profile is valid JSON, values use the registered 0–10 scale, and the API exposes /compatibility/v2/canonical.";
  }
};
