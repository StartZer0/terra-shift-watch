export type Source = 'landsat'|'sentinel2'|'hls_l30'|'hls_s30'|'modis'|'sentinel1';
export type Theme = 'water'|'vegetation'|'forest'|'ground'|'coast';
export interface Settings {
  longitude:number; latitude:number; side_km:number; source:Source; mode:'history'|'event';
  from_year:number; to_year:number; start_month:number; end_month:number; before_date:string; after_date:string;
  window_days:number; resolution:number; max_scenes:number; theme:Theme; themes:Theme[]; aoi_polygon:number[][]|null; use_sam:boolean; use_reasoning:boolean; use_weather:boolean; label:string;
}
export interface Observation {index:number;label:string;year:number;state:'ready'|'missing';date?:string;image?:string;source_image?:string;valid_pct?:number;scene_count?:number;reason?:string;scenes:Array<{id:string;date:string;platform:string;valid_pct:number}>}
export interface Result {
 request:Settings;grid:{resolution_m:number;size:number;bounds:number[];polygon:{coordinates:number[][][]}};
 observations:Observation[];comparison:{before_index:number;after_index:number;before_label:string;after_label:string};
 metrics:Record<string,number|number[]|null>;annual:Array<{year:number;index:number;label:string;water_ha?:number;ndvi?:number|null;bsi?:number|null;mean_vv_db?:number|null}>;
 assessment?:Assessment;
 sam:Array<{index:number;themes?:Theme[];concept?:string;state:string;image?:string;area_ha?:number|null;spectral_iou?:number|null;objects?:number;reason?:string;prompt_mode?:string;object_details?:Array<{id:string;confidence:number|null;mask_pixels:number}>;attempts?:Array<{mode:string;objects:number;request_id:string}>}>;
 sam_summary?:Partial<Record<Theme,SamSummary>>;
 theme_results?:Partial<Record<Theme,{change_image:string}>>;selection_area_km2?:number;
 narrative:null|Narrative;
 weather:null|{dataset:string;resolution:string;baseline:string;annual:Array<{year:number;precipitation_mm:number;temperature_c:number;precipitation_anomaly_mm:number;temperature_anomaly_c:number}>;attribution:string};
 limitations:string[];notes:string[];quality:string;method_status:string;change_image:string;attribution:string;
 traces:Array<{model:string;request_id:string;estimated_usd:number;seconds:number;prompt?:string}>;
 selection?:{index:number;image:string;area_ha:number;objects:number};
 forest_reference?:{state:string;dataset?:string;reason?:string;reference_coverage_pct?:number;canopy_threshold_pct?:number;attribution?:string;limitations?:string[]}|null;
 terrain_reference?:{state:string;dataset?:string;reason?:string;minimum_elevation_m?:number;maximum_elevation_m?:number;mean_slope_degrees_in_exposed_change?:number|null;limitation?:string;attribution?:string}|null;
}
export interface SamSummary {
 concept:string|null;successful:number;attempted:number;guided:number;empty:number;failed:number;common_valid_pct:number;scope:string;support_ha:number;note:string;
 points:Array<{index:number;label:string;value:number|null}>;periods:number;
 change:null|{before_ha:number;after_ha:number;gain_ha:number;loss_ha:number;net_ha:number;image:string};
}
export interface Assessment {
 temporal:{mode:string;requested:string;observed:string;first_year:number;last_year:number;span_years:number;available_periods:number;requested_periods:number;season:string;measurement_basis:string;before_image_date:string;after_image_date:string};
 cards:Array<{theme:Theme;title:string;value:string;unit:string;detail:string;affected_ha:number|null;extent_pct:number|null;extent_label:string;scope:string;coverage_pct:number|null}>;
 features?:Partial<Record<Theme,FeatureFinding>>;
 maps:Partial<Record<Theme,{image:string;title:string;kind?:'reference';legend:Array<{label:string;color:string}>;note:string}>>;
 level_method:string;
 rainfall:null|{annual:Array<{year:number;precipitation_mm:number;precipitation_anomaly_pct:number|null;temperature_anomaly_c:number}>;baseline:string;note:string;reference:string};
}
export interface Narrative {summary:string;observations:Array<{text:string;metric_keys:string[]}>;limitations:string[];by_theme?:Partial<Record<Theme,Narrative>>}
export interface FeatureFinding {
 metrics:Array<{label:string;value:string;unit:string}>;
 chart:null|{title:string;unit:string;color:string;note:string;periods:number;type?:'bars';points:Array<{index:number;label:string;value:number|null}>};
 explanation:string;limitation:string;
}
export interface JobState {state:'running'|'complete'|'failed';stage:string;progress:number;elapsed_seconds?:number;result?:Result}
export class ApiError extends Error { constructor(message:string,public status:number){super(message)} }
export interface SourceInfo {id:Source;name:string;start:number;resolution:number;description:string;kind:string;status:string}

export async function api<T>(url:string,options?:RequestInit):Promise<T> {
 const r=await fetch('/api'+url,{...options,headers:{'Content-Type':'application/json',...options?.headers}});
 if(!r.ok){let message='The request could not complete.';try{const d=await r.json();message=typeof d.detail==='string'?d.detail:d.detail?.map((e:{msg:string})=>e.msg).join('; ')||message}catch{}throw new ApiError(message,r.status)}
 return r.json();
}
