// Automatic overflow pagination.
//
// When a slide uses `paging: auto`, content taller than one slide is split
// into continuation slides at block boundaries instead of being scaled down:
// - Atomic blocks (code, tables, figures, admonitions, ...) are never broken
//   unless explicitly allowed via split_code / split_tables.
// - Lists may break at item boundaries (split_lists); ordered lists keep
//   continuous numbering across pages via the `start` attribute.
// - A page that spills gets a "Continued" marker at its footer, and the
//   continuation page gets a matching marker at the top.
// - A single block too tall for one slide is kept intact and flagged with a
//   visible overflow badge instead of being silently clipped.

(function () {
    "use strict";

    const CONTINUED_TEXT = "Continued →";
    const CONTINUED_FROM_TEXT = "→ Continued";
    const OVERFLOW_BADGE_TEXT = "⚠ Content overflows one slide";
    const MAX_PAGES_PER_SLIDE = 50;
    const TOLERANCE = 1; // px

    function getConfig(container) {
        const cfg = {
            mode: "scale",
            splitLists: true,
            splitCode: false,
            splitTables: false,
        };
        try {
            Object.assign(cfg, JSON.parse(container.dataset.paging || "{}"));
        } catch (e) {
            console.warn("moffee: invalid data-paging config, using defaults.", e);
        }
        return cfg;
    }

    // The element whose direct children are the pagination units. A single
    // paragraph chunk paginates by its rendered blocks; nested chunk layouts
    // (=== / <->) are treated as atomic units.
    function unitWrapper(container) {
        const auto = container.querySelector(".auto-sizing");
        if (!auto) return null;
        const kids = auto.children;
        if (kids.length === 1 && kids[0].classList.contains("chunk-paragraph")) {
            return kids[0];
        }
        return auto;
    }

    function makeMarker(className, text) {
        const el = document.createElement("div");
        el.className = className;
        el.textContent = text;
        return el;
    }

    // Vertical space to keep clear at the bottom of the content area so the
    // footer continuation marker never overlaps content.
    function computeFooterReserve(container) {
        const slideContent = container.querySelector(".slide-content");
        const content = container.querySelector(".content");
        if (!slideContent || !content) return 0;
        const marker = makeMarker("slide-continued", CONTINUED_TEXT);
        marker.style.visibility = "hidden";
        slideContent.appendChild(marker);
        const markerTop = marker.getBoundingClientRect().top;
        marker.remove();
        const contentBottom = content.getBoundingClientRect().bottom;
        return Math.max(0, contentBottom - markerTop) + 4;
    }

    function isHeading(el) {
        return /^H[1-6]$/.test(el.tagName);
    }

    // --- Unit splitters: keep the head part on the current page, return the
    // remainder element (inserted right after the unit), or null if the unit
    // cannot or should not be split here.

    function splitList(list, availBottom) {
        const items = Array.from(list.children).filter((el) => el.tagName === "LI");
        if (items.length < 2) return null;
        let keep = 0;
        for (const li of items) {
            if (li.getBoundingClientRect().bottom <= availBottom - TOLERANCE) keep++;
            else break;
        }
        if (keep === 0 || keep === items.length) return null;
        const clone = list.cloneNode(false);
        if (list.tagName === "OL") {
            const start = parseInt(list.getAttribute("start") || "1", 10);
            clone.setAttribute("start", String(start + keep));
        }
        items.slice(keep).forEach((li) => clone.appendChild(li));
        list.after(clone);
        return clone;
    }

    function splitTable(table, availBottom) {
        const bodies = table.tBodies;
        const rows = bodies.length
            ? Array.from(bodies[0].rows)
            : Array.from(table.rows).filter((r) => !r.closest("thead"));
        if (rows.length < 2) return null;
        let keep = 0;
        for (const tr of rows) {
            if (tr.getBoundingClientRect().bottom <= availBottom - TOLERANCE) keep++;
            else break;
        }
        if (keep === 0 || keep === rows.length) return null;
        const clone = table.cloneNode(false);
        if (table.tHead) clone.appendChild(table.tHead.cloneNode(true));
        const targetBody = bodies.length ? bodies[0].cloneNode(false) : clone;
        if (bodies.length) clone.appendChild(targetBody);
        rows.slice(keep).forEach((tr) => targetBody.appendChild(tr));
        table.after(clone);
        return clone;
    }

    // Split a code block after the last line that still fits, preserving
    // syntax highlight spans on both sides. Accepts either a bare <pre> or a
    // wrapper (e.g. pymdownx emits <div class="highlight"><pre>...).
    function splitCodeBlock(unit, availBottom) {
        const pre = unit.tagName === "PRE" ? unit : unit.querySelector("pre");
        if (!pre) return null;
        const target = pre.querySelector("code") || pre;
        const style = getComputedStyle(target);
        let lineHeight = parseFloat(style.lineHeight);
        if (isNaN(lineHeight)) lineHeight = parseFloat(style.fontSize) * 1.2;
        const preStyle = getComputedStyle(pre);
        const chrome =
            parseFloat(preStyle.paddingTop) +
            parseFloat(preStyle.paddingBottom) +
            parseFloat(preStyle.borderTopWidth) +
            parseFloat(preStyle.borderBottomWidth);
        const top = pre.getBoundingClientRect().top;
        const keepLines = Math.floor((availBottom - top - chrome) / lineHeight);
        const totalLines = (target.textContent.match(/\n/g) || []).length + 1;
        if (keepLines < 1 || keepLines >= totalLines) return null;

        // Locate the text node and offset just after the keepLines-th newline.
        const textNodes = [];
        const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) textNodes.push(node);
        let seen = 0;
        let splitNode = null;
        let splitOffset = -1;
        for (const tn of textNodes) {
            const newlines = [];
            let i = -1;
            while ((i = tn.data.indexOf("\n", i + 1)) !== -1) newlines.push(i);
            if (seen + newlines.length >= keepLines) {
                splitNode = tn;
                splitOffset = newlines[keepLines - seen - 1] + 1;
                break;
            }
            seen += newlines.length;
        }
        if (!splitNode) return null;

        const remainderTarget = target.cloneNode(true);
        const remainderTextNodes = [];
        const walker2 = document.createTreeWalker(remainderTarget, NodeFilter.SHOW_TEXT);
        while ((node = walker2.nextNode())) remainderTextNodes.push(node);
        const splitNode2 = remainderTextNodes[textNodes.indexOf(splitNode)];
        if (!splitNode2) return null;

        // Trim the original after the split point.
        let range = document.createRange();
        range.setStart(splitNode, splitOffset);
        range.setEnd(target, target.childNodes.length);
        range.deleteContents();
        // Trim the remainder before the split point.
        range = document.createRange();
        range.setStart(remainderTarget, 0);
        range.setEnd(splitNode2, splitOffset);
        range.deleteContents();

        // Rebuild the remainder with the same ancestor chain (pre, wrapper
        // divs) so styling applies identically on the next page.
        let remainderBlock = remainderTarget;
        let ancestor = target.parentElement;
        while (ancestor && ancestor !== unit.parentElement) {
            const clone = ancestor.cloneNode(false);
            clone.appendChild(remainderBlock);
            remainderBlock = clone;
            ancestor = ancestor.parentElement;
        }
        unit.after(remainderBlock);
        return remainderBlock;
    }

    function trySplitUnit(unit, availBottom, cfg) {
        switch (unit.tagName) {
            case "UL":
            case "OL":
                return cfg.splitLists ? splitList(unit, availBottom) : null;
            case "TABLE":
                return cfg.splitTables ? splitTable(unit, availBottom) : null;
            case "PRE":
            case "DIV":
                // Bare <pre> or a code wrapper whose only child is a <pre>
                // (div.highlight). Other divs (admonitions, mermaid, ...)
                // stay atomic.
                if (
                    cfg.splitCode &&
                    (unit.tagName === "PRE" ||
                        (unit.children.length === 1 &&
                            unit.firstElementChild.tagName === "PRE"))
                ) {
                    return splitCodeBlock(unit, availBottom);
                }
                return null;
            default:
                return null;
        }
    }

    // --- Continuation slides

    function makeContinuation(current) {
        const next = current.cloneNode(true);
        next.classList.remove("slide-overflow");
        next
            .querySelectorAll(".slide-continued, .slide-continued-from, .slide-overflow-badge")
            .forEach((el) => el.remove());
        const wrapper = unitWrapper(next);
        if (wrapper) wrapper.innerHTML = "";
        current.after(next);

        const currentContent = current.querySelector(".slide-content");
        if (currentContent && !currentContent.querySelector(".slide-continued")) {
            currentContent.appendChild(makeMarker("slide-continued", CONTINUED_TEXT));
        }
        const nextContent = next.querySelector(".slide-content");
        if (nextContent) {
            nextContent.appendChild(makeMarker("slide-continued-from", CONTINUED_FROM_TEXT));
        }
        return next;
    }

    function moveToNextPage(current, firstNode) {
        const next = makeContinuation(current);
        const nextWrapper = unitWrapper(next);
        let node = firstNode;
        while (node) {
            const following = node.nextElementSibling;
            nextWrapper.appendChild(node);
            node = following;
        }
        return next;
    }

    function flagOverflow(container, unit) {
        if (!container.classList.contains("slide-overflow")) {
            container.classList.add("slide-overflow");
            const slideContent = container.querySelector(".slide-content");
            if (slideContent) {
                slideContent.appendChild(makeMarker("slide-overflow-badge", OVERFLOW_BADGE_TEXT));
            }
        }
        console.warn(
            "moffee: block taller than one slide cannot be paginated:",
            unit.tagName,
            unit
        );
    }

    function paginateContainer(container, cfg) {
        const reserve = computeFooterReserve(container);
        let current = container;
        let guard = 0;

        while (guard++ < MAX_PAGES_PER_SLIDE) {
            const wrapper = unitWrapper(current);
            const content = current.querySelector(".content");
            if (!wrapper || !content) break;
            const availBottom = content.getBoundingClientRect().bottom - reserve;
            const usableHeight = content.clientHeight - reserve;
            const units = Array.from(wrapper.children);
            if (!units.length) break;

            const overflowIdx = units.findIndex(
                (u) => u.getBoundingClientRect().bottom > availBottom + TOLERANCE
            );
            if (overflowIdx === -1) break;
            const unit = units[overflowIdx];

            // 1. Fill the current page by splitting the overflowing unit.
            const remainder = trySplitUnit(unit, availBottom, cfg);
            if (remainder) {
                current = moveToNextPage(current, remainder);
                continue;
            }

            // 2. The first unit alone overflows and cannot be split: keep it
            //    intact, flag it, and paginate the rest normally.
            if (overflowIdx === 0) {
                if (unit.getBoundingClientRect().height > usableHeight + TOLERANCE) {
                    flagOverflow(current, unit);
                }
                if (units.length === 1) break;
                current = moveToNextPage(current, units[1]);
                continue;
            }

            // 3. Move the unit (and everything after it) to a continuation
            //    page, keeping headings attached to the block they introduce.
            let moveStart = unit;
            while (
                moveStart.previousElementSibling &&
                moveStart.previousElementSibling !== wrapper.firstElementChild &&
                isHeading(moveStart.previousElementSibling)
            ) {
                moveStart = moveStart.previousElementSibling;
            }
            current = moveToNextPage(current, moveStart);
        }
    }

    function renumberSlides() {
        const all = document.querySelectorAll(".slide-container");
        all.forEach((container, i) => {
            const numEl = container.querySelector(".slide-number p");
            if (!numEl) return;
            numEl.textContent = numEl.textContent.includes("/")
                ? `${i + 1} / ${all.length}`
                : String(i + 1);
        });
    }

    function paginateAll() {
        document.querySelectorAll(".slide-container").forEach((container) => {
            const cfg = getConfig(container);
            if (cfg.mode === "auto") paginateContainer(container, cfg);
        });
        renumberSlides();
        if (typeof window.refreshSlides === "function") window.refreshSlides();
    }

    window.addEventListener("load", paginateAll);
    window.triggerPaginate = paginateAll;
})();
