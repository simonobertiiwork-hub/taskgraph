import http from 'k6/http';

export const options = {
    vus: 100,          // 100 виртуальных пользователей
    duration: '10s',  // нагрузка 10 секунд
};

export default function () {
    http.get('http://localhost:8000/tasks/slow');
}