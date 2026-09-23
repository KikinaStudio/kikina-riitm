#version 330
// Fait avancer chaque particule d'une image. Un pixel de la texture = une particule.
// Contenu : x, y, âge (s), durée de vie (s).
//
// Deux forces se disputent chaque grain :
//   le repos : une attraction douce vers le bas du mur, la matière se dépose ;
//   l'agitation : tourbillons, remous et soulèvement, la matière se réveille.
// L'agitation vient de l'éveil global (la musique) et de l'excitation locale (les visiteurs).
#include "commun.glsl"

uniform sampler2D etat;
uniform sampler2D champs;
uniform sampler2D remous;
uniform sampler2D excitation;    // agitation locale, 0 à 1
uniform float dt;
uniform int image;
uniform float eveil;             // agitation globale, 0 à 1
uniform float repos_hauteur;     // où la matière se dépose (0 = haut, 1 = bas)
uniform float repos_force;
uniform float repos_etalement;   // épaisseur de la nappe au repos (en hauteurs)
uniform float turbulence_repos;  // vitesse du courant au repos (hauteurs/s)
uniform float turbulence_eveil;  // ... à l'éveil maximal
uniform float remous_force;      // vitesse des remous à l'agitation maximale
uniform float soulevement;       // vitesse de montée là où ça s'agite
uniform vec2 vie;                // durée de vie mini et maxi (s)
uniform float onde_poussee;      // vitesse donnée par le front d'une note
out vec4 sortie;

void main() {
    ivec2 tc = ivec2(gl_FragCoord.xy);
    vec4 e = texelFetch(etat, tc, 0);
    uint id = uint(tc.y * textureSize(etat, 0).x + tc.x);
    vec2 u = vec2(e.x / aspect, e.y);

    float allure = 0.4 + 1.2 * hasard(id * 7U + 3U);     // chaque grain a sa vitesse : profondeur
    float local = texture(excitation, u).r;
    float a = clamp(eveil + local, 0.0, 1.0);

    vec2 v = texture(champs, u).gb * mix(turbulence_repos, turbulence_eveil, a);
    v += texture(remous, u).rg * remous_force * a * a;
    float mienne = repos_hauteur + (hasard(id * 19U + 2U) - 0.5) * repos_etalement;  // chaque grain a sa hauteur de repos
    v.y += (mix(mienne, 0.5, a) - e.y) * repos_force * (1.0 - 0.8 * a);
    // là où ça s'agite, chaque grain s'envole vers sa propre hauteur : la matière emplit le mur sans s'entasser en haut
    float envol = 0.1 + 0.8 * hasard(id * 11U + 9U);
    v.y += (envol - e.y) * soulevement * 2.0 * local;
    vec2 pousse;
    fronts(e.xy, pousse);
    v += pousse * onde_poussee;                          // le front d'une note pousse la matière
    // les bords freinent : la matière ne s'entasse ni en haut ni en bas
    v.y *= mix(smoothstep(0.0, 0.08, e.y), smoothstep(1.0, 0.92, e.y), step(0.0, v.y));
    e.xy += v * allure * dt;
    e.x = mod(e.x, aspect);
    e.y = clamp(e.y, 0.003, 0.997);
    e.z += dt;

    if (e.z > e.w) {                                     // renaît ailleurs, en fondu
        // 3 endroits tirés au hasard, on garde le plus dense : les grains naissent dans les masses
        uint g = id * 31U + uint(image) * 2654435761U;
        vec2 ou = vec2(0.0);
        float mieux = -1.0;
        for (uint k = 0U; k < 3U; k++) {
            vec2 c = vec2(hasard(g + k * 5U), hasard(g + k * 5U + 1U));
            c.y = mix(c.y, mix(repos_hauteur, 0.5, eveil), 0.5);   // plutôt là où la matière vit
            float note = texture(champs, c).r + 0.2 * hasard(g + k * 5U + 2U);
            if (note > mieux) { mieux = note; ou = c; }
        }
        e = vec4(ou.x * aspect, ou.y, 0.0, mix(vie.x, vie.y, hasard(g + 20U)));
    }
    sortie = e;
}
