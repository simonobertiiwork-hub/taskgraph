import http from 'k6/http';

export const options = {
    scenarios: {
        users_growth: {
            executor: 'ramping-vus',

            startVUs: 0,

            stages: [
                { duration: '10s', target: 10 },   // лёгкая нагрузка
                { duration: '10s', target: 50 },   // средняя нагрузка
                { duration: '10s', target: 150 },  // высокая нагрузка
            ],

            gracefulRampDown: '0s',
        },
    },
};

export default function () {
    // случайная задержка от 3 до 10 секунд
    const delay = Math.floor(Math.random() * 8) + 3;

    http.get(
        `http://localhost:8000/tasks/slow?delay=${delay}`
    );
}