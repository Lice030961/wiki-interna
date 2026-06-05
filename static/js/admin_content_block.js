(function () {
    var NEEDS_FILE    = ['image', 'video'];
    var NEEDS_CONTENT = ['text', 'checklist', 'link'];

    var LABELS = {
        text:      { content: 'Texto',        placeholder: 'Conteúdo em Markdown ou texto simples.' },
        checklist: { content: 'Itens',        placeholder: 'Um item por linha.' },
        link:      { content: 'URL',          placeholder: 'https://...' },
        image:     { content: 'Legenda',      placeholder: 'Legenda opcional da imagem.' },
        video:     { content: 'Legenda',      placeholder: 'Legenda opcional do vídeo.' },
    };

    function row(fieldName) {
        return document.querySelector('.field-' + fieldName);
    }

    function update(type) {
        var fileRow    = row('file');
        var contentRow = row('content');
        var contentTextarea = document.getElementById('id_content');

        if (fileRow)    fileRow.style.display    = NEEDS_FILE.includes(type)    ? '' : 'none';
        if (contentRow) contentRow.style.display = NEEDS_CONTENT.includes(type) ? '' : 'none';

        if (contentTextarea && LABELS[type]) {
            var label = contentRow && contentRow.querySelector('label');
            if (label) label.textContent = LABELS[type].content + ':';
            contentTextarea.placeholder = LABELS[type].placeholder;
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var select = document.getElementById('id_block_type');
        if (!select) return;
        update(select.value);
        select.addEventListener('change', function () { update(this.value); });
    });
})();
