import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'; // Import the 'path' module

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: { // Add resolve configuration
    alias: {
      '@': path.resolve(__dirname, './src'), // Define the '@' alias
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
