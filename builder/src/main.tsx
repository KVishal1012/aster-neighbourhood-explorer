import React from 'react';
import ReactDOM from 'react-dom/client';
import PlanningExplorer from './planning/PlanningExplorer';
import 'maplibre-gl/dist/maplibre-gl.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><PlanningExplorer/></React.StrictMode>);
