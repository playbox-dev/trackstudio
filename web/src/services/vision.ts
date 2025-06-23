import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const getVisionProcessorSchema = async () => {
  const response = await axios.get(`${API_BASE_URL}/api/vision/config/schema`);
  return response.data;
};

export const getVisionProcessorConfig = async () => {
  const response = await axios.get(`${API_BASE_URL}/api/vision/config`);
  return response.data;
};

export const updateVisionProcessorConfig = async (params: Record<string, any>) => {
  const response = await axios.post(`${API_BASE_URL}/api/vision/config`, { params });
  return response.data;
};

export const restartVisionSystem = async (preserveCalibration: boolean = true) => {
  const response = await axios.post(`${API_BASE_URL}/api/vision/restart`, {
    preserve_calibration: preserveCalibration
  });
  return response.data;
};
