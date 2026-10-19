function dashboardAdmin() {
    return {
        aba: 'modelos',
        adminKey: localStorage.getItem('caborer_admin_key') || '',
        modelos: [],
        aplicacoes: [],
        
        init() {
            if (this.adminKey) {
                this.carregarModelos();
                this.carregarAplicacoes();
            }
        },

        testarConexao() {
            localStorage.setItem('caborer_admin_key', this.adminKey);
            alert('Chave salva com sucesso!');
            this.carregarModelos();
            this.carregarAplicacoes();
        },

        async carregarModelos() {
            try {
                let res = await fetch('/v1/modelos/');
                if (res.ok) this.modelos = await res.json();
            } catch (e) { console.error(e); }
        },

        async carregarAplicacoes() {
            try {
                let res = await fetch('/v1/aplicacoes/', {
                    headers: { 'X-Admin-Key': this.adminKey }
                });
                if (res.ok) this.aplicacoes = await res.json();
            } catch (e) { console.error(e); }
        },

        async listarChaves(appId) {
            let res = await fetch(`/v1/aplicacoes/${appId}/chaves`, {
                headers: { 'X-Admin-Key': this.adminKey }
            });
            if (res.ok) {
                let chaves = await res.json();
                alert(JSON.stringify(chaves, null, 2));
            }
        }
    }
}