#version 330
// Aperçu : le bandeau découpé en 4 lignes, une par mur, à la même échelle.
uniform sampler2D image;
uniform vec4 murs_debut;   // en fraction de la largeur
uniform vec4 murs_fin;
in vec2 uv;
out vec4 sortie;

void main() {
    float y = (1.0 - uv.y) * 4.0;
    int mur = int(y);
    float t = fract(y);
    float plus_long = max(max(murs_fin[0] - murs_debut[0], murs_fin[1] - murs_debut[1]),
                          max(murs_fin[2] - murs_debut[2], murs_fin[3] - murs_debut[3]));
    float x = murs_debut[mur] + uv.x * plus_long;
    vec3 c = vec3(0.12);
    if (x <= murs_fin[mur] && t > 0.015 && t < 0.985)
        c = texture(image, vec2(x, (t - 0.015) / 0.97)).rgb;
    sortie = vec4(c, 1.0);
}
