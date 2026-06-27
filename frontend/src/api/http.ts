import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const http = axios.create({
  baseURL: API_URL,
  timeout: 8000
});
