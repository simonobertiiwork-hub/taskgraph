import http from 'k6/http';

export const options = {
    stages: [
        {duration: '5s', target: 500},
        {duration: '5s', target: 1000},
        {duration: '5s', target: 1000},
    ],
};

export default function () {
    http.get('http://localhost:8000/tasks/slow');
}