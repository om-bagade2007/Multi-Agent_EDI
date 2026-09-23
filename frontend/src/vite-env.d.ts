/// <reference types="vite/client" />
interface ImportMetaEnv { readonly VITE_SIMULATION_MODE?: string; readonly VITE_BASEMAP?: 'carto-light' | 'none' }
interface ImportMeta { readonly env: ImportMetaEnv }
declare module '*.css';
