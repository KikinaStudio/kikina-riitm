#version 330
// Fait avancer chaque particule d'une image. Un pixel de la texture = une particule.
// Contenu : x, y, âge (s), durée de vie (s).
#include "commun.glsl"

uniform sampler2D etat;
uniform sampler2D champs;
uniform float dt;
uniform int image;
uniform float vitesse;      // hauteurs de bandeau par seconde
uniform float chute;        // dérive vers le bas : la matière se dépose
uniform vec2 vie;           // durée de vie mini et maxi (s)
out vec4 sortie;

void main() {
    ivec2 tc = ivec2(gl_FragCoord.xy);
    vec4 e = texelFetch(etat, tc, 0);
    uint id = uint(tc.y * textureSize(etat, 0).x + tc.x);

    float allure = 0.4 + 1.2 * hasard(id * 7U + 3U);     // chaque grain a sa vitesse : profondeur
    vec2 v = texture(champs, vec2(e.x / aspect, e.y)).gb * vitesse * allure + vec2(0.0, chute * allure);
    e.xy += v * dt;
    e.x = mod(e.x, aspect);
    e.z += dt;

    if (e.z > e.w || e.y < -0.02 || e.y > 1.02) {        // renaît ailleurs, en fondu
        // 3 endroits tirés au hasard, on garde le plus dense : les grains naissent dans les masses
        uint g = id * 31U + uint(image) * 2654435761U;
        vec2 ou = vec2(0.0);
        float mieux = -1.0;
        for (uint k = 0U; k < 3U; k++) {
            vec2 c = vec2(hasard(g + k * 5U), hasard(g + k * 5U + 1U));
            float note = texture(champs, c).r + 0.2 * hasard(g + k * 5U + 2U);
            if (note > mieux) { mieux = note; ou = c; }
        }
        e = vec4(ou.x * aspect, ou.y, 0.0, mix(vie.x, vie.y, hasard(g + 20U)));
    }
    sortie = e;
}
