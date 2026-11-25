import java.lang.reflect.*;
import java.util.*;

/** Lê o arquivo com o parser do jogo instalado, sem abrir uma partida. */
public final class VerificarWorldmap {
    public static void main(String[] args) throws Exception {
        Class<?> pathClass = Class.forName("zombie.asset.AssetPath");
        Class<?> managerClass = Class.forName("zombie.asset.AssetManager");
        Class<?> dataClass = Class.forName("zombie.worldMap.WorldMapData");
        Object path = pathClass.getConstructor(String.class).newInstance(args[0]);
        Object data = dataClass.getConstructor(pathClass, managerClass).newInstance(path, null);
        Class<?> readerClass = Class.forName("zombie.worldMap.WorldMapBinary");
        Object reader = readerClass.getConstructor().newInstance();
        boolean loaded = (Boolean) readerClass.getMethod("read", String.class, dataClass)
                .invoke(reader, args[0], data);
        if (!loaded) throw new IllegalStateException("O parser do jogo recusou o worldmap.");
        dataClass.getMethod("onLoaded").invoke(data);
        List<?> cells = (List<?>) dataClass.getField("cells").get(data);
        int features = 0;
        for (Object cell : cells) {
            for (Field field : cell.getClass().getFields()) {
                if (field.getName().equals("features")) features += ((List<?>) field.get(cell)).size();
            }
        }
        System.out.println("WORLD_MAP_GAME_PARSER_OK cells="+cells.size()+" features="+features
                +" minX="+dataClass.getField("minX").get(data)
                +" minY="+dataClass.getField("minY").get(data)
                +" maxX="+dataClass.getField("maxX").get(data)
                +" maxY="+dataClass.getField("maxY").get(data));
        int expected = args.length > 1 ? Integer.parseInt(args[1]) : 4;
        if (cells.size() != expected || features == 0) throw new IllegalStateException("Quantidade de celulas ou feicoes incorreta.");
    }
}
