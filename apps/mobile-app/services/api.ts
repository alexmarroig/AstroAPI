import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';
const API_KEY = 'test-key'; // Mudar para variável de ambiente em produção
const FIXED_USER_ID = 'camila@gmail.com';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Authorization': `Bearer ${API_KEY}`,
    'X-User-Id': FIXED_USER_ID,
    'Content-Type': 'application/json',
  },
});

export const astroService = {
  getNatalChart: async (data: any) => {
    const response = await api.post('/v1/chart/natal', data);
    return response.data;
  },

  getDailySummary: async (params: any) => {
    const response = await api.get('/v1/daily/summary', { params });
    return response.data;
  },

  getCosmicWeather: async (params: any) => {
    const response = await api.get('/v1/cosmic-weather', { params });
    return response.data;
  },

  getTransitEvents: async (data: any) => {
    const response = await api.post('/v1/transits/events', data);
    return response.data;
  },

  getAccountStatus: async () => {
    const response = await api.get('/v1/account/status');
    return response.data;
  },

  chatWithAI: async (data: any) => {
    const response = await api.post('/v1/ai/cosmic-chat', data);
    return response.data;
  }
};

export default api;
