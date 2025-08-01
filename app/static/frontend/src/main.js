import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';

const BACKEND_BASE_URL = 'http://127.0.0.1:8001';

async function waitForReady() {
  const maxRetries = 15;
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(`${BACKEND_BASE_URL}/readyz`);
      if (res.ok) return true;
    } catch {}
    await new Promise(r => setTimeout(r, 1000));
  }
  throw new Error("Backend not ready after retries");
}

async function waitForValidBBox(retries = 10, delay = 3000) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`${BACKEND_BASE_URL}/api/bbox`);
      const bbox = await res.json();
      if (bbox && bbox.min_lat != null) return bbox;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  throw new Error("BBOX not ready after retries.");
}

async function initApp() {
  try {
    await waitForReady();
    const bbox = await waitForValidBBox();
    await initMap(bbox);
  } catch (err) {
    console.error("Startup failed:", err.message);
    document.getElementById('loading').innerText = "Backend not ready.";
  }
}

window.addEventListener('DOMContentLoaded', initApp);
let waypoints = [];  // global declaration

async function initMap(bbox) {
  const center = [
    (bbox.min_lon + bbox.max_lon) / 2,
    (bbox.min_lat + bbox.max_lat) / 2,
  ];

  // Fetch the start location for the drone
  const startRes = await fetch(`${BACKEND_BASE_URL}/api/start_location?drone_id=drone_alpha01`);
  const start = await startRes.json();

  const map = new maplibregl.Map({
    container: 'map',
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors',
        },
      },
      layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
    },
    center,
    zoom: 13,
  });

  if (!start.lon || !start.lat) {
    console.error("Invalid start location:", start);
    return;
  }

  map.fitBounds(
    [
      [bbox.min_lon, bbox.min_lat],
      [bbox.max_lon, bbox.max_lat],
    ],
    { padding: 20 }
  );

  map.on('load', async () => {
    try {
      const droneId = "drone_alpha01";
      const interval = "1 second";
      const traceRes = await fetch(`${BACKEND_BASE_URL}/api/resample?drone_id=${droneId}&interval=${encodeURIComponent(interval)}&cb=${Date.now()}`);
      const traceData = await traceRes.json();
      document.getElementById('play-btn').disabled = false;
      document.getElementById('pause-btn').disabled = false;
      document.getElementById('reset-btn').disabled = false;

      const coordinates = traceData.map(pt => [pt.lon, pt.lat]);
      const animatedCoordinates = [coordinates[0]];

      let marker = new maplibregl.Marker({
        color: '#93378dff',
        draggable: false,
        anchor: 'center',
      })
        .setLngLat([coordinates[0][0], coordinates[0][1]])
        .addTo(map);
    
      map.addSource('drone-path', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [{
            type: 'Feature',
            geometry: { type: 'LineString', coordinates: animatedCoordinates },
            properties: {}
          }],
        }
      });

      map.addLayer({
        id: 'drone-path-line',
        type: 'line',
        source: 'drone-path',
        paint: { 'line-color': '#ce8888ff', 'line-width': 3 },
      });

      function interpolateCoords(start, end, steps) {
        const latDiff = (end[1] - start[1]) / steps;
        const lonDiff = (end[0] - start[0]) / steps;
        const result = [];
        for (let i = 1; i <= steps; i++) {
          result.push([start[0] + lonDiff * i, start[1] + latDiff * i]);
        }
        return result;
      }

      let i = 0;
      let segmentSteps = [];
      let animationFrame;
      const stepsPerSegment = 25;

      async function animateMarkerLoop() {
        const statusRes = await fetch(`${BACKEND_BASE_URL}/status`);
        const state = await statusRes.json();
        if (state.paused) return;

        if (segmentSteps.length === 0 && i < coordinates.length - 1) {
          segmentSteps = interpolateCoords(coordinates[i], coordinates[i + 1], stepsPerSegment);
          i += 1;
        }

        if (segmentSteps.length > 0) {
          const pos = segmentSteps.shift();
          marker.setLngLat(pos);

          waypoints.forEach((wp, index) => {
            const dist = Math.hypot(wp.lon - pos[0], wp.lat - pos[1]);
            if (dist < 0.00025 && !wp.shown) {
              wp.shown = true;  // Prevent showing repeatedly

              const popup = new maplibregl.Popup({ offset: 15, closeOnClick: false })
                .setLngLat([wp.lon, wp.lat])
                .setHTML(`
                  <strong>Waypoint ${index + 1}</strong><br/>
                  Lat: ${wp.lat.toFixed(4)}<br/>
                  Lon: ${wp.lon.toFixed(4)}<br/>
                  ${wp.description || ''}
                `)
                .addTo(map);

              // Auto-dismiss after 1.5 seconds
              setTimeout(() => {
                popup._container.classList.add("fade-out");
                setTimeout(() => popup.remove(), 800);  // Remove after fade
              }, 1500);
            }
          });

          if (animatedCoordinates.length > 1000) {
            animatedCoordinates.shift();
          }
          animatedCoordinates.push(pos);

          map.getSource('drone-path').setData({
            type: 'FeatureCollection',
            features: [{
              type: 'Feature',
              geometry: { type: 'LineString', coordinates: animatedCoordinates },
              properties: {}
            }],
          });

          setTimeout(() => {
            animationFrame = requestAnimationFrame(animateMarkerLoop);
          }, 90);
        }
      }

      function resetMarker() {
        i = 0;
        segmentSteps = [];
        animatedCoordinates.length = 0;
        animatedCoordinates.push(coordinates[0]);
        marker.setLngLat([coordinates[0][0] + 0.00005, coordinates[0][1] + 0.00005]);

        map.getSource('drone-path').setData({
          type: 'FeatureCollection',
          features: [{
            type: 'Feature',
            geometry: { type: 'LineString', coordinates: animatedCoordinates },
            properties: {}
          }],
        });
      }

      async function sendCommand(endpoint) {
        await fetch(`${BACKEND_BASE_URL}/api/${endpoint}`, { method: 'POST' });

        if (endpoint === 'reset') {
          cancelAnimationFrame(animationFrame);
          resetMarker();
        } else if (endpoint === 'play') {
          const statusRes = await fetch(`${BACKEND_BASE_URL}/status`);
          const state = await statusRes.json();
          if (!state.paused) animateMarkerLoop();
        } else if (endpoint === 'pause') {
          cancelAnimationFrame(animationFrame);
        }
      }

      document.getElementById('play-btn').addEventListener('click', () => sendCommand('play'));
      document.getElementById('pause-btn').addEventListener('click', () => sendCommand('pause'));
      document.getElementById('reset-btn').addEventListener('click', () => sendCommand('reset'));

      document.getElementById('loading').style.display = 'none';
      document.getElementById('map').style.display = 'block';

      try {
        const wpRes = await fetch(`${BACKEND_BASE_URL}/api/waypoints`);
        waypoints = await wpRes.json();

        const startCoord = coordinates[0];
        const features = [];

        waypoints.forEach((wp, index) => {
          const distance = Math.hypot(wp.lon - startCoord[0], wp.lat - startCoord[1]);
          if (distance < 0.00005) return;

          features.push({
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [wp.lon, wp.lat],
            },
            properties: {
              description: `
                <strong>Waypoint ${index + 1}</strong><br/>
                Lat: ${wp.lat.toFixed(4)}<br/>
                Lon: ${wp.lon.toFixed(4)}<br/>
                ${wp.description || ''}
              `
            }
          });
        });

        map.addSource('invisible-waypoints', {
          type: 'geojson',
          data: {
            type: 'FeatureCollection',
            features: features,
          }
        });

        map.addLayer({
          id: 'invisible-waypoints-layer',
          type: 'circle',
          source: 'invisible-waypoints',
          paint: {
            'circle-radius': 1,
            'circle-color': '#000000',
            'circle-opacity': 0,  // fully transparent
          }
        });

        map.on('click', 'invisible-waypoints-layer', (e) => {
          const coords = e.features[0].geometry.coordinates;
          const html = e.features[0].properties.description;

          new maplibregl.Popup({ offset: 15 })
            .setLngLat(coords)
            .setHTML(html)
            .addTo(map);
        });

        map.on('mouseenter', 'invisible-waypoints-layer', () => {
          map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', 'invisible-waypoints-layer', () => {
          map.getCanvas().style.cursor = '';
        });
      } catch (err) {
        console.error('Failed to load waypoints', err);
      }
    } catch (err) {
      console.error('Failed to load drone path:', err);
    }
  });
} 