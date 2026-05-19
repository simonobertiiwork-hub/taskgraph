import http from 'k6/http';

export const options = {
    scenarios: {
        low_load: {
            executor: 'constant-vus',
            vus: 10,
            duration: '10s',
        },
        medium_load: {
            executor: 'constant-vus',
            vus: 100,
            duration: '10s',
            startTime: '10s',  // ждём 10с после старта первого сценария
        },
        high_load: {
            executor: 'constant-vus',
            vus: 1000,
            duration: '10s',
            startTime: '20s',  // ждём ещё 10с
        },
    },
};

export default function () {
    http.get('http://localhost:8000/tasks/slow');
}