#version 330
// Les champs, calculés en petite taille une fois par image puis lus par tout le reste :
//   rouge = le voile : où la matière est présente (1) et où elle laisse du vide (0)
//   vert, bleu = le courant qui emporte les grains
#include "commun.glsl"

uniform float voile_echelle;    // taille des grandes masses
uniform float voile_vitesse;    // lenteur de leur respiration
uniform float voile_plein;      // 0 = presque tout est vide, 1 = presque tout est rempli
uniform float voile_filaments;  // 0 = masses pleines, 1 = masses déchirées en filaments
in vec2 uv;
out vec4 sortie;

void main() {
    vec2 u = vec2(uv.x * aspect, uv.y);
    float t = temps * voile_vitesse;
    vec2 c = courant(u);
    vec2 v = u + c * 0.25;                       // les masses épousent les tourbillons
    float masses = nuage(vec2(v.x, v.y * 1.4), t, voile_echelle, 4);
    float seuil = mix(0.57, 0.36, voile_plein);
    masses = smoothstep(seuil - 0.06, seuil + 0.08, masses);
    float f = nuage(vec2(v.x, v.y * 1.8), t * 1.7 + 20.0, voile_echelle * 2.5, 3);
    f = 1.0 - abs(2.0 * f - 1.0);                         // crêtes : des veines plutôt que des taches
    f = smoothstep(0.6, 0.95, f);
    sortie = vec4(masses * mix(1.0, f, voile_filaments), c, 1.0);
}
