-- Prévia local à região: usa os próprios dados vetoriais do protótipo.
require "OptionScreens/MapSpawnSelect"

if MapSpawnSelect and not MapSpawnSelect.CRCPreviewInstalled then
    MapSpawnSelect.CRCPreviewInstalled = true
    local previousRender = MapSpawnSelect.render
    local directory = "media/maps/CriciumaCentroTeste"
    local MIN_X, MIN_Y, MAX_X, MAX_Y = 25600, 25600, 26623, 26623

    local function localPreviewStyle(panel)
        -- O estilo padrão inicializa WorldMapVisited antes de existir uma partida.
        -- A prévia não precisa de exploração/visibilidade do mapa salvo.
        local api = panel.javaObject:getAPIv1()
        api:setBackgroundRGBA(219/255, 215/255, 192/255, 1)
        local style = api:getStyleAPI()
        style:clear()
        for _, def in ipairs({
            {"crc-water", "water", "river", 59, 141, 149},
            {"crc-path", "highway", "trail", 185, 122, 87},
            {"crc-road", "highway", "secondary", 110, 108, 102},
        }) do
            local layer = style:newPolygonLayer(def[1])
            layer:setFilter(def[2], def[3])
            layer:setMinZoom(0)
            layer:addFill(0, def[4], def[5], def[6], 255)
            layer:addFill(24, def[4], def[5], def[6], 255)
        end
    end

    local function restoreOriginal(self, panel)
        panel:clear()
        if self.crcSavedPyramid then
            panel:setImagePyramid(self.crcSavedPyramid)
        else
            for _, region in ipairs(self:getSpawnRegions() or {}) do
                local info = getMapInfo(region.name)
                if info then
                    panel:initMapData("media/maps/" .. region.name)
                    for _, dir in ipairs(info.lots or {}) do
                        panel:initMapData("media/maps/" .. dir)
                    end
                end
            end
        end
        self.crcPreviewActive = false
        self.selectedMapIndex = nil
    end

    function MapSpawnSelect:render()
        local item = self.listbox and self.listbox.items[self.listbox.selected]
        local selected = item and item.item
        local panel = self.mapPanel
        local isCriciuma = selected and selected.dir == "CriciumaCentroTeste"
        if panel and isCriciuma and not self.crcPreviewActive then
            self.crcSavedPyramid = panel.pyramidFileName
            panel:clear()
            panel:initMapData(directory)
            localPreviewStyle(panel)
            panel.mapAPI:setBoolean("ImagePyramid", false)
            panel.mapAPI:setBoolean("HideUnvisited", false)
            panel.mapAPI:setBoundsInSquares(MIN_X, MIN_Y, MAX_X, MAX_Y)
            panel.mapAPI:resetView()
            panel.mapAPI:centerOn(selected.zoomX, selected.zoomY)
            panel.mapAPI:setZoom(selected.zoomS)
            panel.hasResetView = true
            panel.shownInitialLocation = true
            self.selectedMapIndex = nil
            self.crcPreviewActive = true
            print("[CRC] Previa da criacao: vetores locais, " .. MIN_X .. "," .. MIN_Y .. " a " .. MAX_X .. "," .. MAX_Y)
        elseif panel and not isCriciuma and self.crcPreviewActive then
            restoreOriginal(self, panel)
        end
        return previousRender(self)
    end
end
