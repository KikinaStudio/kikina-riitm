#version 330
// Image finale : matière + brume + grain + plancher de gris. Noir et blanc strict.
#include "commun.glsl"

uniform sampler2D champs;
uniform sampler2D matiere;     // lumière accumulée des particules
uniform float exposition;
uniform float brume;           // lueur diffuse là où la matière est dense
uniform float plancher;        // jamais de noir pur : 0.02 à 0.04
uniform float grain_px;        // taille du grain en px (à scale 1)
uniform float grain_force;     // part du grain dans la matière
uniform int grain_image;       // change quelques fois par seconde
uniform float echelle;
in vec2 uv;
out vec4 sortie;

void main() {
    float m = texture(matiere, uv).r;

    ivec2 g = ivec2(gl_FragCoord.xy / (grain_px * echelle));
    float grain = hasard3(ivec3(g, grain_image));
    float grain_gros = hasard3(ivec3(g / 3, grain_image + 7919));
    grain = mix(grain, grain_gros, 0.3);

    float v = texture(champs, uv).r;
    float l = 1.0 - exp(-(m * exposition + brume * v * v));
    l *= 1.0 - grain_force + 2.0 * grain_force * grain;
    l = plancher * (0.5 + grain) + l * (1.0 - plancher);
    sortie = vec4(vec3(clamp(l, 0.0, 1.0)), 1.0);
}
