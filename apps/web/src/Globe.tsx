import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import * as C from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import type {Settings,Result,Theme} from './types';

export interface GlobeHandle {fly:(lon:number,lat:number,side?:number)=>void;home:()=>void;top:()=>void;search:(query:string)=>Promise<Array<{label:string;latitude:number;longitude:number}>>}
interface Props {settings:Settings;polygon:number[][]|null;result:Result|null;jobId:string|null;frame:number;view:string;opacity:number;split:number;showSam:boolean;showSelection:boolean;picking:boolean;drawing:boolean;drawPoints:number[][];activeTheme:Theme;showIntensity:boolean;changeSource:'spectral'|'sam';onVertex:(index:number,lon:number,lat:number)=>void;onPick:(lon:number,lat:number,fly?:boolean)=>void;onResize:(km:number)=>void;onError:(s:string)=>void;watchAreas?:Array<{id:string;label:string;longitude:number;latitude:number;level:number}>;onWatchSelect?:(id:string)=>void;watchLayers?:Array<{url:string;bounds:number[];opacity?:number}>}
export default forwardRef<GlobeHandle,Props>(function Globe(props,ref){
 const container=useRef<HTMLDivElement>(null), viewer=useRef<C.Viewer|null>(null), polygon=useRef<C.Entity|null>(null);
 const handles=useRef<C.Entity[]>([]);
 const draftEntities=useRef<C.Entity[]>([]);
 const watchEntities=useRef<C.Entity[]>([]);
 const latest=useRef(props);latest.current=props;
 const [failed,setFailed]=useState(false);
 useImperativeHandle(ref,()=>({
  async search(query){
   const v=viewer.current;if(!v)throw new Error('Globe is still loading.');
   const matches=await new C.IonGeocoderService({scene:v.scene}).geocode(query);
   return matches.slice(0,6).map(match=>{
    for(const credit of C.GeocoderService.getCreditsFromResult(match)||[])v.creditDisplay.addStaticCredit(credit);
    const p=match.destination instanceof C.Rectangle?C.Rectangle.center(match.destination):C.Cartographic.fromCartesian(match.destination);
    v.scene.requestRender();return {label:match.displayName,latitude:C.Math.toDegrees(p.latitude),longitude:C.Math.toDegrees(p.longitude)};
   });
  },
  fly(lon,lat,side=25){viewer.current?.camera.flyTo({destination:C.Cartesian3.fromDegrees(lon,lat,Math.max(side*2100,18000)),orientation:{heading:0,pitch:-Math.PI/2,roll:0},duration:1.7})},
  home(){viewer.current?.camera.flyTo({destination:C.Cartesian3.fromDegrees(latest.current.settings.longitude,latest.current.settings.latitude,17000000),duration:1.7})},
  top(){const s=latest.current.settings;viewer.current?.camera.flyTo({destination:C.Cartesian3.fromDegrees(s.longitude,s.latitude,s.side_km*2100),orientation:{heading:0,pitch:-Math.PI/2,roll:0},duration:1.2})}
 }),[]);
 useEffect(()=>{
  if(!container.current)return;
  let gone=false; let v:C.Viewer;
  try{
   C.Ion.defaultAccessToken=import.meta.env.VITE_CESIUM_ION_TOKEN||'';
   v=new C.Viewer(container.current,{baseLayer:false,baseLayerPicker:false,animation:false,timeline:false,geocoder:false,homeButton:false,sceneModePicker:false,navigationHelpButton:false,fullscreenButton:false,infoBox:false,selectionIndicator:false,requestRenderMode:true,maximumRenderTimeChange:Infinity,contextOptions:{webgl:{alpha:false,powerPreference:'low-power'}},skyBox:false});
   viewer.current=v;v.resolutionScale=Math.min(1,1.5/window.devicePixelRatio);v.scene.globe.tileCacheSize=80;v.scene.globe.maximumScreenSpaceError=3;v.scene.backgroundColor=C.Color.fromCssColorString('#07131e');v.scene.globe.baseColor=C.Color.fromCssColorString('#143747');v.scene.globe.enableLighting=false;v.scene.fog.enabled=true;
   v.camera.setView({destination:C.Cartesian3.fromDegrees(-105,22,17000000),orientation:{heading:0,pitch:-Math.PI/2,roll:0}});
   C.IonImageryProvider.fromAssetId(2).then(provider=>{if(!gone){v.imageryLayers.addImageryProvider(provider,0);v.scene.requestRender()}}).catch(()=>{if(!gone)latest.current.onError('Globe imagery could not load. Check the Cesium token; coordinates and analysis remain available.')});
   const handler=new C.ScreenSpaceEventHandler(v.scene.canvas);
   let dragging:string|null=null;
   handler.setInputAction((event:{position:C.Cartesian2})=>{
    if(latest.current.drawing)return;
    const picked=v.scene.pick(event.position);
    if(picked?.id instanceof C.Entity&&/^(terra-handle-|terra-vertex-)/.test(String(picked.id.id))){
     dragging=String(picked.id.id);v.scene.screenSpaceCameraController.enableInputs=false;
    }
   },C.ScreenSpaceEventType.LEFT_DOWN);
   handler.setInputAction((event:{endPosition:C.Cartesian2})=>{
    if(!dragging)return;const ray=v.camera.getPickRay(event.endPosition);if(!ray)return;
    const cart=v.scene.globe.pick(ray,v.scene);if(!cart)return;const geo=C.Cartographic.fromCartesian(cart);
    if(dragging.startsWith('terra-vertex-'))latest.current.onVertex(Number(dragging.slice('terra-vertex-'.length)),C.Math.toDegrees(geo.longitude),C.Math.toDegrees(geo.latitude));
    else if(dragging==='terra-handle-center')latest.current.onPick(C.Math.toDegrees(geo.longitude),C.Math.toDegrees(geo.latitude),false);
    else{const s=latest.current.settings;const distance=new C.EllipsoidGeodesic(C.Cartographic.fromDegrees(s.longitude,s.latitude),geo).surfaceDistance;latest.current.onResize(Math.min(500,Math.max(1,Math.round(distance*Math.SQRT2/100)/10)))}
    v.scene.requestRender();
   },C.ScreenSpaceEventType.MOUSE_MOVE);
   handler.setInputAction(()=>{dragging=null;v.scene.screenSpaceCameraController.enableInputs=true},C.ScreenSpaceEventType.LEFT_UP);
   handler.setInputAction((event:{position:C.Cartesian2})=>{
    const entity=v.scene.pick(event.position)?.id;
    if(entity instanceof C.Entity&&String(entity.id).startsWith('watch-')){latest.current.onWatchSelect?.(String(entity.id).slice(6));return}
    if(!latest.current.picking&&!latest.current.drawing)return;
    const ray=v.camera.getPickRay(event.position);if(!ray)return;
    const p=v.scene.globe.pick(ray,v.scene);if(!p)return;
    const geo=C.Cartographic.fromCartesian(p);latest.current.onPick(C.Math.toDegrees(geo.longitude),C.Math.toDegrees(geo.latitude));
   },C.ScreenSpaceEventType.LEFT_CLICK);
   v.screenSpaceEventHandler.removeInputAction(C.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
   const release=()=>{dragging=null;v.scene.screenSpaceCameraController.enableInputs=true};window.addEventListener('pointerup',release);
   return()=>{gone=true;window.removeEventListener('pointerup',release);handler.destroy();v.destroy();viewer.current=null};
  }catch{setFailed(true);props.onError('3D rendering is unavailable in this browser. Use coordinate entry and the image comparison view.');}
 },[]);
 useEffect(()=>{
  const v=viewer.current;if(!v)return;
  watchEntities.current.forEach(e=>v.entities.remove(e));
  const colors=['#89bfae','#e5bd62','#ec934c','#e36e63'];
  watchEntities.current=(props.watchAreas||[]).map(a=>v.entities.add({id:'watch-'+a.id,position:C.Cartesian3.fromDegrees(a.longitude,a.latitude),point:{pixelSize:13,color:C.Color.fromCssColorString(colors[a.level]||'#93a6b1'),outlineColor:C.Color.fromCssColorString('#102937'),outlineWidth:3,disableDepthTestDistance:Number.POSITIVE_INFINITY},label:{text:a.label,font:'13px sans-serif',fillColor:C.Color.WHITE,outlineColor:C.Color.fromCssColorString('#102937'),outlineWidth:4,style:C.LabelStyle.FILL_AND_OUTLINE,pixelOffset:new C.Cartesian2(0,-23),distanceDisplayCondition:new C.DistanceDisplayCondition(0,15000000),disableDepthTestDistance:Number.POSITIVE_INFINITY}}));
  v.scene.requestRender();
 },[props.watchAreas]);
 useEffect(()=>{
  const v=viewer.current;if(!v)return;let cancelled=false;const layers:C.ImageryLayer[]=[];
  const load=async()=>{for(const item of props.watchLayers||[]){try{const provider=await C.SingleTileImageryProvider.fromUrl(item.url,{rectangle:C.Rectangle.fromDegrees(...item.bounds as [number,number,number,number])});if(cancelled)return;const layer=v.imageryLayers.addImageryProvider(provider);layer.alpha=item.opacity??1;layers.push(layer);v.scene.requestRender()}catch{if(!cancelled)latest.current.onError('Satellite preview expired or could not load. Inspect the area again.')}}};void load();
  return()=>{cancelled=true;layers.forEach(l=>{if(!v.isDestroyed())v.imageryLayers.remove(l)});if(!v.isDestroyed())v.scene.requestRender()};
 },[props.watchLayers]);
 useEffect(()=>{
  const v=viewer.current;if(!v)return;
  if(polygon.current)v.entities.remove(polygon.current);
  handles.current.forEach(h=>v.entities.remove(h));handles.current=[];
  if(props.polygon){const positions=props.polygon.map(p=>C.Cartesian3.fromDegrees(p[0],p[1]));polygon.current=v.entities.add({polygon:{hierarchy:new C.PolygonHierarchy(positions),material:C.Color.fromCssColorString('#d9e6ee').withAlpha(.035)},polyline:{positions,width:2,material:C.Color.fromCssColorString('#e6eff5'),clampToGround:true}})}
  if(props.polygon){
   const custom=!!props.settings.aoi_polygon;
   const centers=custom?props.polygon.slice(0,-1):[[props.settings.longitude,props.settings.latitude],...props.polygon.slice(0,4)];
   handles.current=centers.map((p,i)=>v.entities.add({id:custom?'terra-vertex-'+i:'terra-handle-'+(i===0?'center':i),position:C.Cartesian3.fromDegrees(p[0],p[1]),point:{pixelSize:custom||i===0?9:7,color:C.Color.fromCssColorString('#e6eff5'),outlineColor:C.Color.fromCssColorString('#176482'),outlineWidth:2,heightReference:C.HeightReference.CLAMP_TO_GROUND,distanceDisplayCondition:new C.DistanceDisplayCondition(0,props.settings.side_km*8000)}}));
  }
  v.scene.requestRender();
 },[props.polygon]);
 useEffect(()=>{
  const v=viewer.current;if(!v)return;
  draftEntities.current.forEach(e=>v.entities.remove(e));draftEntities.current=[];
  if(props.drawing){
   const positions=props.drawPoints.map(p=>C.Cartesian3.fromDegrees(p[0],p[1]));
   if(positions.length>1)draftEntities.current.push(v.entities.add({polyline:{positions:positions.length>2?[...positions,positions[0]]:positions,width:3,material:C.Color.fromCssColorString('#72dfcc'),clampToGround:true}}));
   positions.forEach(p=>draftEntities.current.push(v.entities.add({position:p,point:{pixelSize:9,color:C.Color.fromCssColorString('#72dfcc'),outlineWidth:2,outlineColor:C.Color.fromCssColorString('#123b45'),heightReference:C.HeightReference.CLAMP_TO_GROUND}})));
  }
  v.scene.requestRender();
 },[props.drawing,props.drawPoints]);
 useEffect(()=>{
  const v=viewer.current;if(!v||!props.result||!props.jobId)return;
  let cancelled=false;const layers:C.ImageryLayer[]=[];const r=props.result;
  const rect=C.Rectangle.fromDegrees(...r.grid.bounds as [number,number,number,number]);
  const add=async(name:string|undefined,split=C.SplitDirection.NONE,alpha=1)=>{
   if(!name)return;
   try{const provider=await C.SingleTileImageryProvider.fromUrl(`/api/jobs/${props.jobId}/assets/${name}`,{rectangle:rect});
    if(cancelled)return;const layer=v.imageryLayers.addImageryProvider(provider);layer.splitDirection=split;layer.alpha=alpha;layers.push(layer);v.scene.requestRender();
   }catch{if(!cancelled)latest.current.onError('A temporary image could not be loaded. The analysis may have expired.')}
  };
  const before=r.observations.find(o=>o.index===r.comparison.before_index),after=r.observations.find(o=>o.index===r.comparison.after_index);
  const current=r.observations.find(o=>o.index===props.frame);
  const load=async()=>{
   if(props.view==='split'){await add(before?.image,C.SplitDirection.LEFT);await add(after?.image,C.SplitDirection.RIGHT)}
   else if(props.view==='before')await add(before?.image);
   else if(props.view==='change'&&props.changeSource==='sam'){await add(after?.image);await add(r.sam_summary?.[props.activeTheme]?.change?.image,C.SplitDirection.NONE,props.opacity)}
   else if(props.view==='change'){await add(after?.image);if(r.assessment?.maps[props.activeTheme]?.kind==='reference'||!r.assessment?.cards.some(c=>c.theme===props.activeTheme&&c.extent_pct===null))await add((props.showIntensity||r.assessment?.maps[props.activeTheme]?.kind==='reference')&&r.assessment?.maps[props.activeTheme]?.image||r.theme_results?.[props.activeTheme]?.change_image||r.change_image,C.SplitDirection.NONE,props.opacity)}
   else await add(current?.image);
   if(props.showSam&&props.view==='after'){const selected=props.showSelection&&r.selection?.index===props.frame?r.selection.image:r.sam.find(s=>s.index===props.frame&&(!s.themes||s.themes.includes(props.activeTheme)))?.image;await add(selected,C.SplitDirection.NONE,props.opacity)}
  };void load();
  return()=>{cancelled=true;layers.forEach(l=>{if(!v.isDestroyed())v.imageryLayers.remove(l)});if(!v.isDestroyed())v.scene.requestRender()};
 },[props.result,props.jobId,props.frame,props.view,props.opacity,props.showSam,props.showSelection,props.activeTheme,props.showIntensity,props.changeSource]);
 useEffect(()=>{const v=viewer.current;if(v){v.scene.splitPosition=props.split;v.scene.requestRender()}},[props.split]);
 return <div ref={container} className={`globe ${props.picking||props.drawing?'picking':''}`} aria-label="Interactive Earth. Use the location controls for keyboard selection.">{failed&&<div className="globe-fallback">3D unavailable · coordinate selection is active</div>}</div>
});
