import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 5 },  // rampa a 5 VU
    { duration: '30s', target: 5 },  // mantieni
    { duration: '10s', target: 0 },  // rampa giù
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],        // meno dell’1% di errori
    http_req_duration: ['p(80)<1200'],      // il 80% sotto 1200ms
  },
};

const BASE_URL = __ENV.BASE_URL || 'https://devopseb47a9-fun.azurewebsites.net';
const ENDPOINT = `${BASE_URL}/api/Trigger`;

const IDS = [
  '000-0000-0e0e00ww-wqesd',
  '000-0000-0e0e00ww-wqe01',
  '000-0000-0e0e00ww-0002e',
  'alert-xx-12-cosmos-giu',
];

export default function () {
  const requests = IDS.map((id) => {
    const url = `${ENDPOINT}?id=${encodeURIComponent(id)}`;
    return {
      method: 'GET',
      url,
      params: {
        headers: {
          'Accept': 'application/json',
        },
        timeout: '30s',
      },
    };
  });

  const responses = http.batch(requests);

  for (let i = 0; i < responses.length; i++) {
    const resp = responses[i];
    check(resp, {
      'status è 2xx': (r) => r.status >= 200 && r.status < 300,
      'body non vuoto': (r) => r.body && r.body.length > 0,
    });
  }

  sleep(1);
}
