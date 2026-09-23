/// <reference types="vite/client" />
interface ImportMetaEnv { readonly VITE_SIMULATION_MODE?: string }
interface ImportMeta { readonly env: ImportMetaEnv }
declare module '*.css';
