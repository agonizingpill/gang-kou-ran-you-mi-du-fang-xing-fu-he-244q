import*as trays from'/workspace/frontend/src/pages/trays.js';
const base={tanks:[{id:1,code:'TK-06',grade:'VLSFO',liters:50000},{id:2,code:'TK-08',grade:'VLSFO',liters:20000},{id:3,code:'TK-M01',grade:'MGO',liters:35000}],
samples:[{id:11,code:'FS-A',tank_id:1,tank_code:'TK-06',grade:'VLSFO',status:'qualified',density_15:980,retest_density:null},{id:12,code:'FS-B',tank_id:3,tank_code:'TK-M01',grade:'MGO',status:'qualified',density_15:852,retest_density:null}],
transfers:[],grades:{},audit:[],trays:[],traySelected:null};
const u={role:'admin'};
// 1. empty
let html=trays.render(base,u);
if(!html.includes('先建立复核盘'))throw new Error('empty state missing');
// 2. draft tray with bottle+candidate
const draft={id:5,code:'LT-01',note:'同盘疑签',state:'draft',bottles_frozen:false,reference_snapshot:null,suggestion:null,adopted_snapshot:null,last_error:'',
bottles:[{id:51,tray_id:5,sample_id:11,original_tank_id:1,assigned_tank_id:null,score:null,sample_code:'FS-A',sample_status:'qualified',original_tank_code:'TK-06',original_grade:'VLSFO',density_15:980,retest_density:null,effective_density:980,assigned_tank_code:null}],
candidates:[{id:61,tray_id:5,tank_id:1,tank_code:'TK-06',grade:'VLSFO'},{id:62,tray_id:5,tank_id:3,tank_code:'TK-M01',grade:'MGO'}]};
base.trays=[draft];base.traySelected=5;
html=trays.render(base,u);
for(const k of['LT-01','登记中','FS-A','原签','执行整盘分析','TK-M01'])if(!html.includes(k))throw new Error('draft missing '+k);
// 3. suggested with matrix
const sug={...draft,state:'suggested',bottles_frozen:true,reference_snapshot:{grades:{VLSFO:{count:60,codes:[],values:[]},MGO:{count:60,codes:[],values:[]}},accepted_by:'admin@chenggang.local',at:'2026-11-18T01:00:00+00:00'},
suggestion:{near_tie:false,tie_epsilon:.5,thresholds:{VLSFO:-1.8,MGO:-1.7},computed_at:'2026-11-18T01:01:00+00:00',
schemes:[{count:2,total_score:-2.3,assignments:[{sample_id:11,sample_code:'FS-A',tank_id:1,tank_code:'TK-06',grade:'VLSFO',score:-1.1},{sample_id:12,sample_code:'FS-B',tank_id:3,tank_code:'TK-M01',grade:'MGO',score:-1.2}],unassigned:[]},
{count:2,total_score:-4.9,assignments:[{sample_id:11,sample_code:'FS-A',tank_id:3,tank_code:'TK-M01',grade:'MGO',score:-3.0},{sample_id:12,sample_code:'FS-B',tank_id:1,tank_code:'TK-06',grade:'VLSFO',score:-1.9}],unassigned:[]}],
matrix:{'11':{'1':{score:-1.1,threshold:-1.8,eligible:true},'3':{score:-3.0,threshold:-1.7,eligible:false}},'12':{'1':{score:-1.9,threshold:-1.8,eligible:true},'3':{score:-1.2,threshold:-1.7,eligible:true}}}},
bottles:[draft.bottles[0],{id:52,tray_id:5,sample_id:12,original_tank_id:3,assigned_tank_id:3,score:-1.2,sample_code:'FS-B',sample_status:'qualified',original_tank_code:'TK-M01',original_grade:'MGO',density_15:852,retest_density:null,effective_density:852,assigned_tank_code:'TK-M01'}]};
sug.bottles[0]={...sug.bottles[0],assigned_tank_id:1,score:-1.1,assigned_tank_code:'TK-06'};
base.trays=[sug];
html=trays.render(base,u);
for(const k of['建议待采纳','分数矩阵','方案1','方案2','主管采纳整盘归属','低于阈值','-1.100'])if(!html.includes(k))throw new Error('suggested missing '+k);
if(html.includes('核签采纳方案'))throw new Error('suggested must not show scheme radio');
// 4. review (near-tie)
const rev={...sug,state:'review',suggestion:{...sug.suggestion,near_tie:true}};
base.trays=[rev];
html=trays.render(base,u);
for(const k of['并列待人工核签','近似并列转人工核签','核签采纳方案','人工核签依据'])if(!html.includes(k))throw new Error('review missing '+k);
// 5. adopted
const ado={...sug,state:'adopted',adopted_by:'admin@chenggang.local',adopted_snapshot:{tray_code:'LT-01',scheme_index:0,scheme:sug.suggestion.schemes[0],changes:[{sample_code:'FS-A',from_tank:'TK-08',to_tank:'TK-06',score:-1.1}],recalled_transfers:['TR-9'],sign_note:'',adopted_by:'admin@chenggang.local',at:'2026-11-18T02:00:00+00:00'}};
base.trays=[ado];
html=trays.render(base,u);
for(const k of['已采纳冻结','整盘归属已采纳冻结','TR-9','换签1瓶','采纳人'])if(!html.includes(k))throw new Error('adopted missing '+k);
if(html.includes('主管采纳整盘归属</button>')&&!html.includes('disabled'))throw new Error('adopted must not allow re-adopt');
// 6. failed
const fail={...draft,state:'failed',bottles_frozen:true,last_error:'参考密度没有足够变化'};
base.trays=[fail];
html=trays.render(base,u);
for(const k of['核算失败可恢复','从原盘恢复重算','参考密度没有足够变化'])if(!html.includes(k))throw new Error('failed missing '+k);
// 7. viewer gating
html=trays.render({...base,trays:[sug]},{role:'viewer'});
const adoptBtn=html.match(/<button class="copper"[^>]*>主管采纳整盘归属<\/button>/);
if(!adoptBtn||!adoptBtn[0].includes('disabled'))throw new Error('viewer adopt not disabled');
console.log('ALL RENDER SMOKE TESTS PASS');
