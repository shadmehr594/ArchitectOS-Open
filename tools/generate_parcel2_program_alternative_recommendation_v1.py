import json,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.architecture.reasoning.program_alternative_recommendation_v1 import ProgramAlternativeRecommendationV1

def main():
 source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/commercial_spatial_quality_tradeoff_v1_*/PARCEL2_COMMERCIAL_SPATIAL_QUALITY_TRADEOFF_V1.json'))[-1]
 checkpoint=json.loads(source.read_text());result=ProgramAlternativeRecommendationV1().resolve(checkpoint);result['source_contract_path']=str(source)
 folder=source.parents[1]/('program_alternative_recommendation_v1_'+datetime.now().strftime('%Y%m%d_%H%M%S'));folder.mkdir();out=folder/'PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps({'json':str(out),'recommendation':result.get('recommended_next_scenario'),'action':result.get('recommended_next_action'),'program_changed':result['program_changed']}))
if __name__=='__main__':main()
