#version 330
// Image finale : matière + brume + grain + plancher de gris. Noir et blanc strict.
#include "commun.glsl"

uniform sampler2D champs;
uniform sampler2D matiere;     // lumière accumulée des particules
uniform sampler2D encre;       // le texte des titres et des cards (1 = blanc)
uniform float fond;            // lumière du panneau d'une card (la colonne qui coupe le mur)
uniform sampler2D atlas;       // les cartes use case rangées en étagères, noir sur blanc
uniform vec4 voyage[24];       // carte en route : x, y (coin haut gauche), largeur, hauteur (largeur 0 = aucune)
uniform vec4 voyage_atlas[24]; // sa place dans l'atlas : u0, v0, u1, v1
uniform float voyage_fondu;    // 1 = visibles, 0 = effacées
uniform float blanc;           // lumière du fond blanc des cartes
uniform vec4 portes[3];
uniform float arrondi;         // rayon des coins des panneaux et des cartes
uniform float carte_grain;     // part du grain gardée sur les panneaux et les cartes (1 = comme la matière)
uniform float exposition;
uniform float brume;           // lueur diffuse là où la matière est dense
uniform float plancher;        // jamais de noir pur : 0.02 à 0.04
uniform float grain_px;        // taille du grain en px (à scale 1)
uniform float grain_force;     // part du grain dans la matière
uniform int grain_image;       // change quelques fois par seconde
uniform float echelle;
in vec2 uv;
out vec4 sortie;

// d : position depuis le coin du rectangle de taille t. Vrai dedans, coins arrondis de rayon arrondi.
bool dedans(vec2 d, vec2 t) {
    vec2 q = abs(d - 0.5 * t) - (0.5 * t - arrondi);
    return length(max(q, 0.0)) <= arrondi;
}

void main() {
    float m = texture(matiere, uv).r;

    ivec2 g = ivec2(gl_FragCoord.xy / (grain_px * echelle));
    float grain = hasard3(ivec3(g, grain_image));
    float grain_gros = hasard3(ivec3(g / 3, grain_image + 7919));
    grain = mix(grain, grain_gros, 0.3);

    float v = texture(champs, uv).r;
    float l = 1.0 - exp(-(m * exposition + brume * v * v));
    // le texte apparaît et s'efface grain par grain, chaque grain à son moment ; il prend le grain de la matière
    vec2 p = vec2(uv.x * aspect, uv.y);
    bool cache = false;              // les cartes en route passent sous les panneaux et derrière les portes (toute la hauteur)
    for (int i = 0; i < 3; i++) cache = cache || (p.x >= portes[i].x && p.x <= portes[i].z);
    float carte = 0.0;               // 1 sur un panneau ou une carte : moins de grain, le texte reste net
    for (int i = 0; i < 8; i++) {
        vec4 s = cartes_etat[i], r = cartes[i];
        if (s.x <= 0.0 || !dedans(p - r.xy, r.zw - r.xy)) continue;
        cache = true;
        carte = s.x;
        float moment = hasard3(ivec3(g, 4242 + i)) * 0.85;
        if (i >= 4) l = max(l, fond * s.x);           // le panneau des cards (pas des titres)
        l = max(l, texture(encre, uv).r * s.z * smoothstep(moment, moment + 0.15, s.x));
    }
    for (int i = 0; i < 24; i++) {
        vec4 v = voyage[i];
        if (cache || v.z <= 0.0) continue;
        vec2 d = vec2(mod(p.x - v.x, aspect), p.y - v.y);  // le bandeau boucle en x
        if (!dedans(d, v.zw)) continue;
        carte = voyage_fondu;
        vec4 a = voyage_atlas[i];
        l = mix(l, texture(atlas, mix(a.xy, a.zw, d / v.zw)).r * blanc, voyage_fondu);
    }
    float gf = grain_force * mix(1.0, carte_grain, carte);
    l *= 1.0 - gf + 2.0 * gf * grain;
    l = plancher * (0.5 + grain) + l * (1.0 - plancher);
    sortie = vec4(vec3(clamp(l, 0.0, 1.0)), 1.0);
}
