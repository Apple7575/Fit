import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { SCENES, type SceneKey } from '../../data/homepageDemo';
import { DemoBrowser, DemoPanel } from './DemoBrowser';

/**
 * Scene 04~08 — 왼쪽 문구가 스크롤에 따라 바뀌고 오른쪽 브라우저 프레임은 고정된 채 탭만 전환된다.
 * 각 Scene 에 따로 sticky 를 붙이지 않고 스테이지 하나만 sticky 다.
 * 모바일(lg 미만)에서는 문구 → 해당 카드 순서의 일반 세로 흐름으로 바꾼다.
 * IntersectionObserver 가 없으면 첫 장면을 보여준다.
 */
export function ProductStory() {
  const [active, setActive] = useState<SceneKey>('overview');
  const articleRefs = useRef<Map<SceneKey, HTMLElement>>(new Map());

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        // 화면 중앙 띠에 들어온 장면을 활성으로 본다
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const key = (entry.target as HTMLElement).dataset.scene as SceneKey;
            setActive(key);
          }
        }
      },
      { rootMargin: '-45% 0px -45% 0px', threshold: 0 },
    );
    articleRefs.current.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <section
      aria-labelledby="product-story-title"
      className="product-story bg-slate-50"
      id="product-story"
    >
      <h2 className="sr-only" id="product-story-title">
        다섯 가지 분석 화면 미리보기
      </h2>

      <div className="product-stage">
        <div className="story-copy">
          {SCENES.map((scene, i) => (
            <article
              className="story-scene"
              data-scene={scene.key}
              id={`scene-${scene.key}`}
              key={scene.key}
              ref={(el) => {
                if (el) articleRefs.current.set(scene.key, el);
                else articleRefs.current.delete(scene.key);
              }}
            >
              <p className="text-sm font-bold text-blue-600">
                {String(i + 1).padStart(2, '0')} · {scene.tab}
              </p>
              <h3 className="scene-title mt-3 font-extrabold tracking-tight text-slate-950">
                {scene.title}
              </h3>
              <p className="body-large mt-5 text-slate-500">{scene.lead}</p>
              <p className="mt-3 text-base leading-7 text-slate-500">{scene.body}</p>
              <Link
                className="mt-6 inline-flex items-center gap-1 text-sm font-bold text-blue-700 underline-offset-4 hover:underline"
                to={scene.path}
              >
                실제 화면에서 보기 <span aria-hidden="true">›</span>
              </Link>

              {/* 모바일: 문구 바로 아래에 해당 카드 */}
              <div className="mt-6 lg:hidden">
                <div className="landing-card">
                  <DemoPanel scene={scene.key} />
                </div>
              </div>
            </article>
          ))}
        </div>

        <div className="story-stage-frame hidden lg:block">
          <DemoBrowser active={active} />
        </div>
      </div>
    </section>
  );
}
