/** @odoo-module **/

import Dialog from 'web.Dialog';

const originalConfirm = Dialog.confirm;

Dialog.confirm = function (title, message, options) {
    const dialog = originalConfirm.call(this, title, message, options);

    // 🔎 Só aplica delay se for o popup da redistribuição
    if (message && message.includes('Redistribuir') || title.includes('Redistribuição')) {
        const $okButton = dialog.$footer.find('.btn-primary');
        let seconds = 5;

        // desabilita botão inicialmente
        $okButton.prop('disabled', true);
        $okButton.text(`OK (${seconds})`);

        // contador regressivo
        const interval = setInterval(() => {
            seconds -= 1;
            if (seconds > 0) {
                $okButton.text(`OK (${seconds})`);
            } else {
                clearInterval(interval);
                $okButton.prop('disabled', false);
                $okButton.text('OK');
            }
        }, 1000);
    }

    return dialog;
};
