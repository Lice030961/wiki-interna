// Tokens da wiki (Desktop + neutros do DESIGN.md). Os mesmos do app Rotas Premium (../route/tailwind.config.js).
// Gerar o CSS depois de mudar classes nos templates/JS:
//   tools\tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify
module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js', './core/**/*.py'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      colors: {
        brand: { red: '#AC2407', redhov: '#8f1d06', yellow: '#EFBC00', yellhov: '#d4a800' },
        // Neutros creme do DESIGN.md
        ink: '#000000',
        body: '#33332e',
        mute: '#62625b',
        ash: '#91918c',
        stone: '#c8c8c1',
        hairline: '#dadad3',
        soft: '#fbfbf9',
        card: '#f6f6f3',
        secondary: '#e5e5e0',
        pressed: '#c8c8c1',
      },
    },
  },
  plugins: [],
};
