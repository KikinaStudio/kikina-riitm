// Fonctions partagées : hasard, bruit continu en x, voile de densité, courant.
// Unités : x de 0 à `aspect` (le tour de la salle), y de 0 (haut) à 1 (bas).

uniform float aspect;     // largeur / hauteur du bandeau
uniform float temps;      // secondes

// Hasard sur des entiers : donne exactement le même résultat sur Mac et sur PC.
uint hacher(uint x) {
    x ^= x >> 16; x *= 0x7feb352dU;
    x ^= x >> 15; x *= 0x846ca68bU;
    x ^= x >> 16;
    return x;
}
float hasard(uint n) { return float(hacher(n)) / 4294967295.0; }
float hasard3(ivec3 p) {
    return float(hacher(uint(p.x) + hacher(uint(p.y) + hacher(uint(p.z))))) / 4294967295.0;
}

// Bruit lisse en 3D (x, y, temps), périodique en x : le bord droit rejoint le bord gauche.
// Bruit "à gradients" : formes rondes, sans alignement visible sur une grille.
float bruit(vec3 p, int periode) {
    ivec3 i = ivec3(floor(p));
    vec3 f = fract(p);
    vec3 s = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    float r = 0.0;
    for (int k = 0; k < 8; k++) {
        ivec3 o = ivec3(k & 1, (k >> 1) & 1, (k >> 2) & 1);
        ivec3 c = i + o;
        c.x = int(mod(float(c.x), float(periode)));
        uint h = hacher(uint(c.x) + hacher(uint(c.y) + hacher(uint(c.z))));
        vec3 g = vec3(h & 1023U, (h >> 10) & 1023U, (h >> 20) & 1023U) / 511.5 - 1.0;
        vec3 w = mix(1.0 - s, s, vec3(o));
        r += dot(normalize(g + 1e-4), f - vec3(o)) * w.x * w.y * w.z;
    }
    return clamp(0.5 + 0.75 * r, 0.0, 1.0);
}

// Bruit à plusieurs échelles. `freq` = nombre de motifs sur la hauteur du bandeau.
float nuage(vec2 u, float t, float freq, int octaves) {
    int n = max(1, int(round(aspect * freq)));   // nombre entier de motifs sur le tour complet
    vec3 p = vec3(u.x / aspect * float(n), u.y * freq, t);
    float r = 0.0, a = 0.5;
    for (int k = 0; k < octaves; k++) {
        r += a * bruit(p, n);
        p.xy *= 2.0; p.z *= 1.3; n *= 2; a *= 0.5;
    }
    return r / (1.0 - a * 2.0);                  // ramené entre 0 et 1
}

// Courant : tourbillons lents, sans source ni puits (la matière ne s'entasse pas).
// Le potentiel s'annule en haut et en bas : le courant longe les bords au lieu de sortir.
uniform float courant_echelle;
uniform float courant_evolution;
float potentiel(vec2 u, float t) {
    float bords = smoothstep(0.0, 0.25, u.y) * (1.0 - smoothstep(0.75, 1.0, u.y));
    return (nuage(u, t, courant_echelle, 2) - 0.5) * bords;
}
vec2 courant(vec2 u) {
    float e = 0.01;
    float t = temps * courant_evolution + 50.0;
    float dy = potentiel(u + vec2(0.0, e), t) - potentiel(u - vec2(0.0, e), t);
    float dx = potentiel(u + vec2(e, 0.0), t) - potentiel(u - vec2(e, 0.0), t);
    return vec2(dy, -dx) / (2.0 * e * courant_echelle);
}

// Remous : même principe, 4 fois plus petit et 6 fois plus vif. Sert à l'agitation.
vec2 courant_fin(vec2 u) {
    float e = 0.004, k = courant_echelle * 4.0;
    float t = temps * courant_evolution * 6.0 + 300.0;
    float b0 = smoothstep(0.0, 0.1, u.y) * (1.0 - smoothstep(0.9, 1.0, u.y));
    #define P(q) ((nuage(q, t, k, 2) - 0.5) * b0)
    float dy = P(u + vec2(0.0, e)) - P(u - vec2(0.0, e));
    float dx = P(u + vec2(e, 0.0)) - P(u - vec2(e, 0.0));
    #undef P
    return vec2(dy, -dx) / (2.0 * e * k);
}

// Les ondes des notes : anneaux qui partent d'un point et s'élargissent.
// Chaque onde : x, y (mêmes unités que les particules), âge (s), force (0 = éteinte).
uniform vec4 ondes[8];
uniform float onde_vitesse;   // hauteurs de bandeau par seconde
uniform float onde_duree;     // s
uniform float onde_largeur;   // épaisseur du front (hauteurs)

// Présence des fronts d'onde au point p (0 = aucun) ; `dir` : poussée vers l'extérieur.
float fronts(vec2 p, out vec2 dir) {
    float s = 0.0;
    dir = vec2(0.0);
    for (int i = 0; i < 8; i++) {
        vec4 o = ondes[i];
        if (o.w <= 0.0) continue;
        vec2 d = p - o.xy;
        d.x -= aspect * round(d.x / aspect);                  // le bandeau boucle en x
        float r = length(d);
        float rayon = onde_vitesse * o.z * (0.5 + o.w);       // une note forte va plus loin
        float vie = smoothstep(0.0, 0.1, o.z) * (1.0 - smoothstep(0.3, 1.0, o.z / onde_duree));
        float f = exp(-pow((r - rayon) / onde_largeur, 2.0)) * o.w * vie;
        s += f;
        dir += d / max(r, 1e-4) * f;
    }
    return s;
}
