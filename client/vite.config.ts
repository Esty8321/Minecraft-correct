// import { defineConfig } from "vite";
// import react from "@vitejs/plugin-react";

// export default defineConfig({
//   plugins: [react()],
//   server: {
//     port: 5173,
//     proxy: {
//       "/auth": {
//         target: "http://localhost:8080",
//         changeOrigin: true,
//       },
//       "/game": {
//         target: "http://localhost:8080",
//         ws: true,
//         changeOrigin: true,
//       },
//     },
//   },
// });


// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // אין צורך ב-historyApiFallback - ב-Vite זה כבר SPA כברירת מחדל
    proxy: {
      // REST של התחברות/הרשמה עובר דרך ה-edge
      "/auth": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },

      // חשוב: מפרקסים רק את ה-WebSocket של המשחק,
      // כדי ש-GET /game ישאר אצל ה-React Router (ולא יגיע ל-edge)
      "^/game/ws": {
        target: "http://localhost:8080",
        ws: true,
        changeOrigin: true,
        secure: false,
      },

      // אם יש גם צ'אט ב-WS
      // "^/chat/ws": {
      //   target: "http://localhost:8080",
      //   ws: true,
      //   changeOrigin: true,
      //   secure: false,
      // },
    },
  },
});
