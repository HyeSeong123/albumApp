window.onload = function () {
    if (!Array.isArray(imageItems)) {
        console.warn('imageItems is not a valid array.');
        return;
    }

    const photoAlbumElement = document.getElementById('photoAlbum');
    const dateRangeElement = document.getElementById('current-page-date-range');

    if (!photoAlbumElement) {
        console.error('photoAlbum element not found');
        return;
    }

    let pageFlipInstance = null;

    function groupImages(items, perPage = 6) {
        const groups = [];
        for (let i = 0; i < items.length; i += perPage) {
            groups.push(items.slice(i, i + perPage));
        }
        return groups;
    }

    function generatePageHTMLs(items) {
        const pages = groupImages(items).map(group => {
            const page = document.createElement('div');
            page.className = 'multi-image-page';
            page.innerHTML = group.map(item => `
                <div class="image-container-with-date">
                    <img src="${item.url}" class="album-image" data-date="${item.date || ''}" data-keywords="${item.keywords || ''}" alt="사진">
                    <div class="image-date-overlay">${item.date || ''}</div>
                </div>
            `).join('');
            return page;
        });

        // 홀수 페이지일 경우 빈 페이지 추가
        if (pages.length % 2 !== 0) {
            const emptyPage = document.createElement('div');
            emptyPage.className = 'empty-notebook-page';
            emptyPage.textContent = '빈 페이지';
            pages.push(emptyPage);
        }

        return pages;
    }

    function initializePageFlip(pages) {
        pageFlipInstance = new St.PageFlip(photoAlbumElement, {
            width: photoAlbumElement.clientWidth / 2,
            height: photoAlbumElement.clientHeight,
            showCover: false,
            size: "fixed",
            flippingTime: 600,
            disableFlipByClick: true,
            clickBottomCornerToFlip: false
        });

        pageFlipInstance.loadFromHTML(pages);

        pageFlipInstance.on('flip', () => {
            updateDateRange();
        });

        updateDateRange();
    }

    function updateDateRange() {
        if (!pageFlipInstance) return;

        const index = pageFlipInstance.getCurrentPageIndex();
        const pages = pageFlipInstance.getPageCollection().getPages();
        let dates = [];

        [index, index + 1].forEach(i => {
            const page = pages[i]?.getElement();
            if (page) {
                const imgs = page.querySelectorAll('.album-image');
                imgs.forEach(img => {
                    if (img.dataset.date) dates.push(new Date(img.dataset.date));
                });
            }
        });

        if (dates.length === 0) {
            dateRangeElement.textContent = '날짜 정보 없음';
            return;
        }

        dates.sort((a, b) => a - b);
        const [start, end] = [dates[0], dates[dates.length - 1]];
        const format = d => d.toISOString().split('T')[0];
        dateRangeElement.textContent = (format(start) === format(end)) ? format(start) : `${format(start)} ~ ${format(end)}`;
    }

    function setup() {
        const pages = generatePageHTMLs(imageItems);
        initializePageFlip(pages);
    }

    if (photoAlbumElement.clientWidth && photoAlbumElement.clientHeight) {
        setup();
    } else {
        setTimeout(setup, 100); // 렌더링 지연 대비
    }

    // 반응형 재설정
    window.addEventListener('resize', () => {
        if (!pageFlipInstance || !pageFlipInstance.getCurrentPageIndex) return;
        const index = pageFlipInstance.getCurrentPageIndex();
        pageFlipInstance.destroy();
        setup();
        pageFlipInstance.turnToPage(index);
    });
};
