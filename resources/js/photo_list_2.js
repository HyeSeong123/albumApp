// photo_list_2.js 내부에서 사용하는 함수 수정
let imageItems = [];
let isFetchingNextBatch = false;

async function fetchInitialImages() {
  try {
    const res = await fetch(`/photo_list_2?offset=${imageItems.length}&limit=12`);
    imageItems = await res.json();
    pageContentHTMLs = generatePageHTMLs(imageItems);

    const width = bookElement.clientWidth / 2;
    const height = bookElement.clientHeight;
    initializeAndLoadPageFlip(width, height);
  } catch (e) {
    console.error('초기 이미지 로드 실패', e);
  }
}

function generatePageHTMLs(imageItems) {
  const pages = [];
  for (let i = 0; i < imageItems.length; i += 6) {
    const pageDiv = document.createElement('div');
    pageDiv.className = 'pf-page';
    pageDiv.style.display = 'grid';
    pageDiv.style.gridTemplateColumns = 'repeat(3, 1fr)';
    pageDiv.style.gridTemplateRows = 'repeat(2, 1fr)';
    pageDiv.style.gap = '0.5rem';
    pageDiv.style.padding = '1rem';
    pageDiv.style.width = '100%';
    pageDiv.style.height = '100%';
    pageDiv.style.boxSizing = 'border-box';
    pageDiv.style.background = '#fff';

    const group = imageItems.slice(i, i + 6);
    group.forEach(item => {
      const wrapper = document.createElement('div');
      wrapper.className = 'image-wrapper';
      wrapper.style.width = '100%';
      wrapper.style.height = '100%';
      wrapper.style.overflow = 'hidden';

      const img = document.createElement('img');
      img.className = 'album-image';
      img.src = item.url;
      img.alt = '사진';
      img.dataset.date = item.date || '';
      img.dataset.keywords = item.keywords || '';
      img.style.width = '100%';
      img.style.height = '100%';
      img.style.objectFit = 'cover';
      img.style.display = 'block';
      img.style.borderRadius = '0.25rem';

      wrapper.appendChild(img);
      pageDiv.appendChild(wrapper);
    });

    pages.push(pageDiv);
  }
  return pages;
}

// ✨ 페이지 넘길 때마다 새 이미지 로드
// 예: 페이지 넘김 이벤트에서 다음 사진 batch 요청
document.addEventListener('pageflip:flip', async function (e) {
  const nextPageIndex = e.data;
  const totalPages = pageFlipInstance.getPageCount();

  if (nextPageIndex >= totalPages - 2 && !isFetchingNextBatch) {
    isFetchingNextBatch = true;
    try {
      const res = await fetch(`/photo_list_2?offset=${imageItems.length}&limit=12`);
      const newItems = await res.json();
      imageItems = imageItems.concat(newItems);
      const newPages = generatePageHTMLs(newItems);
      pageFlipInstance.updateFromHtml(newPages);
    } catch (err) {
      console.error('사진 추가 로드 실패:', err);
    } finally {
      isFetchingNextBatch = false;
    }
  }
});

document.addEventListener('DOMContentLoaded', fetchInitialImages);
