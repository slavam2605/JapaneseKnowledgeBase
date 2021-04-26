package server

import java.io.File
import java.lang.reflect.Modifier

object ComponentContainerManager {
    private val contentMap = mutableMapOf<Class<*>, Any>()

    inline fun <reified T: Any> registerContent(value: T) {
        registerContent(T::class.java, value)
    }

    inline fun <reified T: Any> getImplementations(): List<T> {
        return getImplementations(T::class.java)
    }

    fun <T: Any> registerContent(clazz: Class<T>, value: T) {
        contentMap[clazz] = value
    }

    fun <T: Any> getImplementations(clazz: Class<T>): List<T> {
        val result = mutableListOf<T>()
        for (root in getClassPathDirectories()) {
            root.walk()
                .filter { file -> file.extension == "class" }
                .mapNotNullTo(result) { file ->
                    val classQualifiedName = file.relativeToOrNull(root)!!
                        .path.substringBeforeLast('.')
                        .replace(File.separatorChar, '.')
                    val foundClass = javaClass.classLoader.loadClass(classQualifiedName)
                    if (!foundClass.isInterface &&
                        !Modifier.isAbstract(foundClass.modifiers) &&
                        clazz.isAssignableFrom(foundClass))
                        createInstance(foundClass) as T?
                    else
                        null
                }
        }
        return result
    }

    private fun <T> createInstance(clazz: Class<T>): T? {
        println("Loading $clazz")
        val ctor = clazz.declaredConstructors[0]
        val arguments = Array<Any?>(ctor.parameterCount) { null }
        ctor.parameterTypes.forEachIndexed { index, type ->
            print("\tLoading ${type.name} argument... ")
            val arg = contentMap.getOrElse(type) {
                println("Failed")
                return null
            }

            arguments[index] = arg
            println("Success")
        }

        return ctor.newInstance(*arguments) as T
    }

    private fun getClassPathDirectories(): List<File> {
        val classPath = System.getProperty("java.class.path")
        val separator = File.pathSeparatorChar
        val parts = classPath.split(separator)
        return parts
            .filter { !it.endsWith(".jar") }
            .map { File(it) }
    }
}