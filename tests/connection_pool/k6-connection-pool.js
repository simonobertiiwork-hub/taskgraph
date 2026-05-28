import http from 'k6/http';

export const options = {
    scenarios: {
        users_growth: {
            executor: 'ramping-vus',

            startVUs: 0,

            stages: [
                {duration: '2s', target: 10},  // лёгкая нагрузка
                {duration: '2s', target: 50},  // средняя нагрузка
                {duration: '2s', target: 150},  // высокая нагрузка
            ],

            gracefulRampDown: '0s',
        },
    },
};

export default function () {
    http.get('http://localhost:8000/tasks/slow');
}