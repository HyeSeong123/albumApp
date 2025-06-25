document.addEventListener('DOMContentLoaded', function () {
    const imageItemsRaw = typeof image_items_json !== 'undefined' ? image_items_json : '[]'; // Ensure image_items_json is defined
    let imageItems = [];
    try {
        if (imageItemsRaw && imageItemsRaw !== 'None') { // 'None' 문자열도 체크
            imageItems = JSON.parse(imageItemsRaw);
        } else {
            console.log('image_items_json is null, undefined, or "None". Initializing imageItems as empty array.');
        }
    } catch (e) {
        console.error("Error parsing image_items_json:", e, "Raw data:", imageItemsRaw);
        // 파싱 오류 시 imageItems는 빈 배열로 유지
    }

    // --- 1. Helper Function Definitions FIRST ---
    function groupImages(items, perPage = 6) {
        const groups = [];
        if (!items || !Array.isArray(items)) return groups;
        for (let i = 0; i < items.length; i += perPage) {
            groups.push(items.slice(i, i + perPage));
        }
        return groups;
    }

    function generatePageHTMLs(currentImageItems) {
        const grouped = groupImages(currentImageItems, 6);
        const htmlElements = grouped.map(group => {
            const pageDiv = document.createElement('div');
            // For PageFlip, pages are typically direct children, not wrapped further unless handled by library
            // The class 'multi-image-page' can be used for styling the content within the page.
            pageDiv.className = 'pf-page multi-image-page'; // Add pf-page for PageFlip library
            pageDiv.innerHTML = group.map(item => {
                const keywords = item.keywords || ''; // undefined 방지
                const date = item.date || ''; // undefined 방지
                return `
                    <div class="image-container-with-date">
                        <img src="${item.url}" class="album-image" alt="사진" data-keywords="${keywords}" data-date="${date}">
                        <div class="image-date-overlay">${date}</div>
                    </div>
                `;
            }).join('');
            
            // Hotspots should be added carefully, PageFlip might have its own way or conflict
            // For simplicity, direct page click handling is often better with custom content.
            // const nextHotspotDiv = document.createElement('div');
            // nextHotspotDiv.className = 'flip-hotspot flip-next-hotspot';
            // pageDiv.appendChild(nextHotspotDiv);

            pageDiv.addEventListener('click', function(event) {
                if (event.target === pageDiv) {
                    event.stopPropagation();
                }
            });

            return pageDiv;
        });
        // Ensure even number of pages if book is two-sided, PageFlip handles this typically by how it renders.
        // If you add an empty page, it should also be a .pf-page
        if (htmlElements.length > 0 && htmlElements.length % 2 !== 0) {
            const emptyRightPage = document.createElement('div');
            emptyRightPage.className = 'pf-page empty-notebook-page'; // Add pf-page
            emptyRightPage.innerHTML = '<div></div>'; // Must have some content for PageFlip
            htmlElements.push(emptyRightPage);
        }
        return htmlElements;
    }

    function openModalWithImage(imageElement, imagesOnThisPageFlipPage, clickedImageIndex) {
        if (!modal) return;
        currentImagesInPageForModal = imagesOnThisPageFlipPage;
        currentImageIndexInModal = clickedImageIndex;
        updateModalContents();
        modal.style.display = "block";
    }

    function updateModalContents() {
        if (!modalImg || !captionText || !prevModalNav || !nextModalNav) return;

        if (currentImagesInPageForModal.length > 0 && currentImagesInPageForModal[currentImageIndexInModal]) {
            const imageData = currentImagesInPageForModal[currentImageIndexInModal];
            modalImg.src = imageData.url;
            let captionHTML = `<strong>${imageData.date || ''}</strong>`;
            if (imageData.keywords && imageData.keywords.trim() !== '') {
                captionHTML += `<br>${imageData.keywords.split(',').filter(k => k.trim() !== '').join(', ')}`;
            }
            captionText.innerHTML = captionHTML;
        }
        const canGoPrevInModal = currentImageIndexInModal > 0;
        const canGoNextInModal = currentImageIndexInModal < currentImagesInPageForModal.length - 1;
        const canGoPrevPageFlip = pageFlipInstance && pageFlipInstance.getCurrentPageIndex && pageFlipInstance.getCurrentPageIndex() > 0;
        const canGoNextPageFlip = pageFlipInstance && pageFlipInstance.getCurrentPageIndex && pageFlipInstance.getPageCount && pageFlipInstance.getCurrentPageIndex() < pageFlipInstance.getPageCount() - 1;

        prevModalNav.style.display = (canGoPrevInModal || canGoPrevPageFlip) ? 'block' : 'none';
        nextModalNav.style.display = (canGoNextInModal || canGoNextPageFlip) ? 'block' : 'none';
    }

    function bindPageContentEventListeners() {
        if (!pageFlipInstance || !bookElement) return;
        // PageFlip.js wraps pages in its own items, typically with class like 'stf__item'
        // Or, if using loadFromHTML with .pf-page, query for those.
        const pageElements = bookElement.querySelectorAll('.pf-page'); 

        pageElements.forEach(pageElement => {
            const imagesInPage = Array.from(pageElement.querySelectorAll('.album-image'));
            
            imagesInPage.forEach((imgElem) => {
                // Re-cloning can sometimes help with event listeners, but ensure it's necessary.
                const newImgElem = imgElem.cloneNode(true);
                imgElem.parentNode.replaceChild(newImgElem, imgElem);
                
                newImgElem.addEventListener('click', function(event) {
                    event.preventDefault(); 
                    event.stopImmediatePropagation(); 
                    const currentImageElementsOnPage = Array.from(this.closest('.pf-page').querySelectorAll('.album-image'));
                    const currentDataset = currentImageElementsOnPage.map(img => ({
                        url: img.src,
                        date: img.dataset.date || '', 
                        keywords: img.dataset.keywords || '' 
                    }));
                    const clickedIndexInPage = currentImageElementsOnPage.indexOf(this);
                    openModalWithImage(this, currentDataset, clickedIndexInPage);
                });

                const parentContainer = newImgElem.closest('.image-container-with-date');
                if (!parentContainer) return;

                let keywordTooltip = parentContainer.querySelector('.keyword-tooltip');
                if (!keywordTooltip) {
                    keywordTooltip = document.createElement('div');
                    keywordTooltip.className = 'keyword-tooltip';
                    parentContainer.appendChild(keywordTooltip);
                }

                newImgElem.addEventListener('mouseenter', function() {
                    this.style.transform = 'scale(1.08)';
                    this.style.transition = 'transform 0.1s ease-out';
                    const keywords = this.dataset.keywords;
                    if (keywords && keywords.trim() !== '') {
                        keywordTooltip.textContent = keywords.split(',').filter(k => k.trim() !== '').join(', ');
                        keywordTooltip.style.display = 'block';
                    } else {
                        keywordTooltip.style.display = 'none';
                    }
                });

                newImgElem.addEventListener('mouseleave', function() {
                    this.style.transform = 'scale(1)';
                    if (keywordTooltip) keywordTooltip.style.display = 'none';
                });
            });
        });
    }

    function updatePageDateRange(currentFlipInstance) {
        if (!currentFlipInstance || typeof currentFlipInstance.getCurrentPageIndex !== 'function') return;

        const currentPageIndex = currentFlipInstance.getCurrentPageIndex();
        const pages = currentFlipInstance.getPageCollection().getPages(); // Use PageFlip API
        const dateRangeElement = document.getElementById('current-page-date-range');
        if (!dateRangeElement) return;

        let datesOnCurrentSpread = [];
        
        const processPage = (pageIndex) => {
            if (pageIndex < pages.length) {
                const pageObject = pages[pageIndex]; // This is a PageObject from the library
                if (pageObject && pageObject.getElement()) {
                    const pageElement = pageObject.getElement();
                    const images = pageElement.querySelectorAll('.album-image');
                    images.forEach(img => {
                        const date = img.dataset.date;
                        if (date) datesOnCurrentSpread.push(date);
                    });
                }
            }
        };

        processPage(currentPageIndex);
        // Consider if the book is showing one or two pages at a time based on settings
        if (currentFlipInstance.getSettings().width * 2 <= bookElement.clientWidth && (currentPageIndex + 1) < pages.length) { 
            processPage(currentPageIndex + 1);
        }

        if (datesOnCurrentSpread.length > 0) {
            const dateObjects = datesOnCurrentSpread.map(d => new Date(d.split(' ')[0])); 
            dateObjects.sort((a, b) => a - b); 
            
            const minDate = dateObjects[0].toISOString().split('T')[0];
            const maxDate = dateObjects[dateObjects.length - 1].toISOString().split('T')[0];

            if (minDate === maxDate) {
                dateRangeElement.textContent = minDate;
            } else {
                dateRangeElement.textContent = `${minDate} ~ ${maxDate}`;
            }
        } else {
            dateRangeElement.textContent = "날짜 정보 없음";
        }
    }

    function initializeAndLoadPageFlip(width, height, startPage = 0) {
        if (!bookElement) return;
        if (pageFlipInstance && typeof pageFlipInstance.destroy === 'function') {
            pageFlipInstance.destroy();
        }
        
        // Ensure St is defined (from page-flip.browser.js)
        if (typeof St === 'undefined' || typeof St.PageFlip === 'undefined') {
            console.error('St.PageFlip is not defined. Make sure page-flip.browser.js is loaded.');
            // Retry or alert user
            setTimeout(() => initializeAndLoadPageFlip(width, height, startPage), 200);
            return;
        }

        initialFlipSettings = {
            width: width,
            height: height,
            showCover: false, // Assuming dynamic pages don't have a separate cover defined this way
            size: "fixed", // As per reference, but 'stretch' might be desired for responsiveness
            flippingTime: 600,
            // clickBottomCornerToFlip: false, // Reference had this
            // disableFlipByClick: true      // Reference had this
            // Consider PageFlip's own settings for click-to-flip, often configurable.
        };

        pageFlipInstance = new St.PageFlip(bookElement, initialFlipSettings);

        if (pageContentHTMLs && pageContentHTMLs.length > 0) {
            pageFlipInstance.loadFromHTML(pageContentHTMLs);
            bindPageContentEventListeners(); 

            updatePageDateRange(pageFlipInstance);

            pageFlipInstance.on('flip', (e) => {
                console.log('Flipped to page:', e.data);
                updatePageDateRange(pageFlipInstance);
                if(modal) modal.style.display = "none"; // Close modal on page flip
            }); 

            if (startPage > 0 && pageFlipInstance.turnToPage) {
                // Ensure page index is valid
                const validStartPage = Math.min(startPage, pageFlipInstance.getPageCount() -1 );
                pageFlipInstance.turnToPage(validStartPage); 
            }
        } else {
            bookElement.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; width:100%; height:100%; font-size:1.2em; color:#777;">표시할 사진이 없습니다.</div>';
        }
    }

    // --- 2. DOM Element Selections & Global Variables ---
    const bookElement = document.getElementById('photoBook'); // Changed from photoAlbumElement
    if (!bookElement) {
        console.error('Photo book element #photoBook not found!');
        return; 
    }
    console.log("Parsed imageItems (from top declaration):", imageItems);

    let pageFlipInstance = null;
    let pageContentHTMLs = [];
    let initialFlipSettings = {};

    const modal = document.getElementById("imageModal");
    const modalImg = document.getElementById("modalImage");
    const captionText = document.getElementById("modalCaption");
    const closeModalButton = document.querySelector(".close-modal-button");
    const prevModalNav = document.querySelector(".prev-modal-nav");
    const nextModalNav = document.querySelector(".next-modal-nav");

    let currentImageIndexInModal = 0; 
    let currentImagesInPageForModal = [];

    // --- 3. Event Handlers for Static Elements ---
    if (closeModalButton) {
        closeModalButton.onclick = function() {
            if(modal) modal.style.display = "none";
        }
    }

    window.addEventListener('click', function(event) {
        if (event.target == modal) {
            if(modal) modal.style.display = "none";
        }
    });

    if (prevModalNav) {
        prevModalNav.onclick = function(e) {
            e.stopPropagation();
            if (currentImageIndexInModal > 0) {
                currentImageIndexInModal--;
                updateModalContents();
            } else if (pageFlipInstance && pageFlipInstance.flipPrev) {
                if(modal) modal.style.display = "none"; // Close modal before flipping
                pageFlipInstance.flipPrev();
            }
        }
    }

    if (nextModalNav) {
        nextModalNav.onclick = function(e) {
            e.stopPropagation();
            if (currentImageIndexInModal < currentImagesInPageForModal.length - 1) {
                currentImageIndexInModal++;
                updateModalContents();
            } else if (pageFlipInstance && pageFlipInstance.flipNext) {
                if(modal) modal.style.display = "none"; // Close modal before flipping
                pageFlipInstance.flipNext(); 
            }
        }
    }
    
    const backButton = document.getElementById('backButton');
    if (backButton) {
        backButton.addEventListener('click', () => {
            window.history.back();
        });
    }

    // --- 4. Initial Logic Execution ---
    // const dateRangeElement = document.getElementById('current-page-date-range'); // Already declared in updatePageDateRange

    if (imageItems && imageItems.length > 0) {
        pageContentHTMLs = generatePageHTMLs(imageItems);
        
        const attemptInitialization = () => {
            // Check if St.PageFlip is available before proceeding
            if (typeof St === 'undefined' || typeof St.PageFlip === 'undefined') {
                console.warn('St.PageFlip not defined yet. Retrying initialization...');
                setTimeout(attemptInitialization, 100); // Retry after a short delay
                return;
            }
            if (bookElement.clientWidth > 0 && bookElement.clientHeight > 0) {
                const initialWidth = bookElement.clientWidth / 2; // Assuming two pages fit container width
                const initialHeight = bookElement.clientHeight;
                initializeAndLoadPageFlip(initialWidth, initialHeight);
            } else {
                console.warn('Book element has no dimensions. Flipbook might not initialize correctly. Retrying...');
                // Retry if dimensions are not ready, common in some rendering scenarios
                setTimeout(attemptInitialization, 100);
            }
        };
        
        attemptInitialization();

    } else {
         bookElement.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; width:100%; height:100%; font-size:1.2em; color:#777;">표시할 사진이 없습니다.</div>';
         console.log("No image items to display or imageItems is not an array.");
    }

    // --- 5. Resize Handler ---
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (!bookElement || !pageFlipInstance || typeof pageFlipInstance.getCurrentPageIndex !== 'function') return;

            const newContainerWidth = bookElement.clientWidth;
            const newContainerHeight = bookElement.clientHeight;

            if (newContainerWidth > 0 && newContainerHeight > 0) {
                const newPageWidth = newContainerWidth / 2;
                const newPageHeight = newContainerHeight;
                
                let currentPageIndex = 0;
                if (pageFlipInstance && typeof pageFlipInstance.getCurrentPageIndex === 'function') {
                     currentPageIndex = pageFlipInstance.getCurrentPageIndex();
                }
                
                // Pass the current page index to maintain position after resize
                initializeAndLoadPageFlip(newPageWidth, newPageHeight, currentPageIndex); 
                console.log('PageFlip re-initialized with new dimensions.');
            } else {
                console.warn('Book element has no dimensions on resize. Skipping PageFlip update.');
            }
        }, 250); 
    });
});
