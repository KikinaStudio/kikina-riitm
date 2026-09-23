#version 330
// Place chaque particule sur le bandeau et décide de sa taille et de sa lumière.
#include "commun.glsl"

uniform sampler2D etat;
uniform sampler2D champs;
uniform sampler2D excitation;
uniform float eveil;
uniform float nombre;          // nombre total de particules
uniform float densite;         // 0 à 1 : part des particules allumées
uniform float taille;          // diamètre moyen en px (à scale 1)
uniform float echelle;         // scale de config.toml
uniform float voile_contraste; // 0 = matière uniforme, 1 = masses et vides marqués
uniform float onde_eclat;      // lumière en plus sur le front d'une note
uniform float scintille;       // frémissement des grains fins (son clair)
out float lumiere;

void main() {
    int l = textureSize(etat, 0).x;
    vec4 e = texelFetch(etat, ivec2(gl_VertexID % l, gl_VertexID / l), 0);
    uint id = uint(gl_VertexID);

    // Les particules s'allument une à une quand la densité monte, sans saut.
    float rang = float(gl_VertexID) / nombre;
    float allumee = clamp((densite - rang) / 0.08 + 0.5, 0.0, 1.0);

    float age = e.z / e.w;
    float fondu = smoothstep(0.0, 0.2, age) * (1.0 - smoothstep(0.75, 1.0, age));

    vec2 u = vec2(e.x / aspect, e.y);
    float masse = mix(1.0, texture(champs, u).r, voile_contraste);
    float a = clamp(eveil + texture(excitation, u).r, 0.0, 1.0);
    masse *= 0.7 + 0.5 * a + 0.8 * texture(excitation, u).r;  // la matière s'éclaire en s'agitant, surtout localement

    // Beaucoup de grains fins et ternes, quelques rares gros et brillants.
    float h = hasard(id * 13U + 1U);
    float gros = pow(h, 12.0);
    lumiere = allumee * fondu * masse * (0.12 + 0.88 * pow(hasard(id * 17U + 5U), 2.5)) * (1.0 + 1.5 * gros);

    vec2 inutile;
    lumiere *= 1.0 + onde_eclat * min(fronts(e.xy, inutile), 1.5);   // le front d'une note s'éclaire
    // son clair : les grains fins frémissent, chacun à son rythme (3 à 7 fois par seconde)
    lumiere *= 1.0 + scintille * (1.0 - gros) * sin(6.2832 * (temps * (3.0 + 4.0 * hasard(id * 23U + 7U)) + hasard(id * 29U + 3U)));

    gl_PointSize = (taille * (0.8 + 1.6 * gros) + 1.0) * echelle;
    gl_Position = lumiere < 0.004
        ? vec4(2.0, 2.0, 0.0, 1.0)                                     // éteinte : hors champ
        : vec4(e.x / aspect * 2.0 - 1.0, e.y * 2.0 - 1.0, 0.0, 1.0);
}
