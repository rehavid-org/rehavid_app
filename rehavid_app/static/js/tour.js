/**
 * REHAVID · Guía interactiva contextual (tour de sección).
 * Uso: window.RehavidTour.init({ id, userKey, steps: [{ selector, title, text }] })
 */
(function () {
  'use strict';

  function claveVisto(id, userKey) {
    return `rehavid:tour:${id}:${userKey || 'anon'}`;
  }

  function yaVisto(id, userKey) {
    try {
      return window.localStorage.getItem(claveVisto(id, userKey)) === '1';
    } catch (e) {
      return false;
    }
  }

  function marcarVisto(id, userKey) {
    try {
      window.localStorage.setItem(claveVisto(id, userKey), '1');
    } catch (e) {
      /* almacenamiento no disponible (modo privado, cuota llena, etc.) */
    }
  }

  function esMovil() {
    return window.matchMedia('(max-width: 860px)').matches;
  }

  function esVisible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  }

  function crearGuia(config) {
    const pasos = (config.steps || []).filter((p) => esVisible(document.querySelector(p.selector)));
    if (!pasos.length) return null;

    let indice = 0;
    let activa = false;

    const raiz = document.createElement('div');
    raiz.className = 'tour-r';
    raiz.innerHTML = `
      <div class="tour-spot" aria-hidden="true"></div>
      <div class="tour-card" role="dialog" aria-modal="true" aria-label="Guía de la sección">
        <button type="button" class="tour-cerrar" data-tour-cerrar aria-label="Cerrar guía">×</button>
        <div class="tour-paso"></div>
        <h3 class="tour-titulo"></h3>
        <p class="tour-texto"></p>
        <div class="tour-pie">
          <div class="tour-puntos"></div>
          <div class="tour-nav">
            <button type="button" class="btn-r mini tour-atras">Atrás</button>
            <button type="button" class="btn-r mini primario tour-sig">Siguiente</button>
          </div>
        </div>
      </div>`;

    const spot = raiz.querySelector('.tour-spot');
    const card = raiz.querySelector('.tour-card');
    const elPaso = raiz.querySelector('.tour-paso');
    const elTitulo = raiz.querySelector('.tour-titulo');
    const elTexto = raiz.querySelector('.tour-texto');
    const puntos = raiz.querySelector('.tour-puntos');
    const btnAtras = raiz.querySelector('.tour-atras');
    const btnSig = raiz.querySelector('.tour-sig');

    puntos.innerHTML = pasos.map(() => '<span class="tour-punto"></span>').join('');
    const puntoEls = puntos.querySelectorAll('.tour-punto');

    function posicionar() {
      const paso = pasos[indice];
      const el = document.querySelector(paso.selector);
      if (!esVisible(el)) {
        if (indice < pasos.length - 1) {
          indice += 1;
          render();
        } else {
          cerrar();
        }
        return;
      }
      el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const pad = 6;
        spot.style.top = `${Math.max(r.top - pad, 0)}px`;
        spot.style.left = `${Math.max(r.left - pad, 0)}px`;
        spot.style.width = `${r.width + pad * 2}px`;
        spot.style.height = `${r.height + pad * 2}px`;

        if (esMovil()) {
          card.classList.add('tour-card--hoja');
          card.style.top = '';
          card.style.left = '';
        } else {
          card.classList.remove('tour-card--hoja');
          const cw = card.offsetWidth || 320;
          const ch = card.offsetHeight || 180;
          let top = r.bottom + 14;
          if (top + ch > window.innerHeight - 12) top = Math.max(r.top - ch - 14, 12);
          let left = Math.min(Math.max(r.left, 12), window.innerWidth - cw - 12);
          card.style.top = `${top}px`;
          card.style.left = `${left}px`;
        }
      });
    }

    function render() {
      const paso = pasos[indice];
      elPaso.textContent = `Paso ${indice + 1} de ${pasos.length}`;
      elTitulo.textContent = paso.title;
      elTexto.textContent = paso.text;
      btnAtras.disabled = indice === 0;
      btnSig.textContent = indice === pasos.length - 1 ? 'Entendido' : 'Siguiente';
      puntoEls.forEach((p, i) => p.classList.toggle('activo', i === indice));
      posicionar();
    }

    function onKeydown(e) {
      if (e.key === 'Escape') cerrar();
      else if (e.key === 'ArrowRight') siguiente();
      else if (e.key === 'ArrowLeft') anterior();
    }

    function siguiente() {
      if (indice < pasos.length - 1) {
        indice += 1;
        render();
      } else {
        cerrar();
      }
    }

    function anterior() {
      if (indice > 0) {
        indice -= 1;
        render();
      }
    }

    function cerrar() {
      if (!activa) return;
      activa = false;
      marcarVisto(config.id, config.userKey);
      window.removeEventListener('keydown', onKeydown);
      window.removeEventListener('resize', posicionar);
      window.removeEventListener('scroll', posicionar, true);
      raiz.remove();
    }

    raiz.querySelectorAll('[data-tour-cerrar]').forEach((b) => b.addEventListener('click', cerrar));
    btnSig.addEventListener('click', siguiente);
    btnAtras.addEventListener('click', anterior);

    return {
      abrir() {
        if (activa) return;
        activa = true;
        indice = 0;
        document.body.appendChild(raiz);
        window.addEventListener('keydown', onKeydown);
        window.addEventListener('resize', posicionar);
        window.addEventListener('scroll', posicionar, true);
        render();
      },
    };
  }

  window.RehavidTour = {
    init(config) {
      const guia = crearGuia(config);
      if (!guia) return;

      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = 'tour-fab';
      boton.setAttribute('aria-label', 'Ver guía de esta sección');
      boton.textContent = '?';
      boton.addEventListener('click', () => guia.abrir());
      document.body.appendChild(boton);

      if (!yaVisto(config.id, config.userKey)) {
        window.setTimeout(() => guia.abrir(), 400);
      }
    },
  };
})();
