/// <reference types="vite/client" />
interface ImportMetaEnv { readonly VITE_SIMULATION_MODE?: string; readonly VITE_BASEMAP?: 'carto-light' | 'osm' | 'none'; readonly VITE_EXPOSE_MAP?: string }
interface ImportMeta { readonly env: ImportMetaEnv }
interface Window { __puneMap?: import('maplibre-gl').Map }
declare module '*.css';
